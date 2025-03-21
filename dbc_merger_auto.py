import re
import os
from collections import defaultdict

def parse_dbc_file(file_path):
    """Parse a DBC file and extract message definitions and other components."""
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Extract components
    version_match = re.search(r'VERSION\s+"([^"]*)"', content)
    version = version_match.group(1) if version_match else ""

    # Extract NS section
    ns_match = re.search(r'NS_\s+:(.*?)BS_\s*:', content, re.DOTALL)
    ns_section = ns_match.group(1).strip() if ns_match else ""

    # Extract bus units (BU)
    bu_match = re.search(r'BU_\s*:(.*?)(?:BO_|VAL_TABLE_)', content, re.DOTALL)
    bus_units = []
    if bu_match:
        bu_line = bu_match.group(1).strip()
        if bu_line:
            bus_units = re.split(r'\s+', bu_line)

    # Extract message definitions (BO_)
    bo_pattern = r'BO_\s+(\d+)\s+([^:]+):\s+(\d+)\s+([^\n]+)(?:\n(?:\s+SG_\s+[^\n]+))*'
    messages = {}
    for match in re.finditer(bo_pattern, content):
        msg_id = int(match.group(1))
        msg_name = match.group(2).strip()
        msg_size = int(match.group(3))
        msg_sender = match.group(4).strip()
        msg_text = match.group(0)

        # Extract signals
        signals = {}
        sg_pattern = r'SG_\s+([^\s:]+)\s*:\s*([^"]+)"([^"]*)"(.*)'
        for sg_match in re.finditer(sg_pattern, msg_text):
            sg_name = sg_match.group(1).strip()
            sg_def = sg_match.group(2).strip()
            sg_unit = sg_match.group(3).strip()
            sg_receivers = sg_match.group(4).strip()
            signals[sg_name] = (sg_def, sg_unit, sg_receivers)

        messages[msg_id] = {
            'name': msg_name,
            'size': msg_size,
            'sender': msg_sender,
            'signals': signals,
            'text': msg_text
        }

    # Extract value definitions (VAL_)
    value_definitions = []
    val_pattern = r'VAL_\s+(\d+)\s+([^;]+);'
    for match in re.finditer(val_pattern, content):
        value_definitions.append(match.group(0))

    # Extract comments (CM_)
    comments = []
    cm_pattern = r'CM_[^;]+;'
    for match in re.finditer(cm_pattern, content):
        comments.append(match.group(0))

    # Extract other sections
    other_sections = []

    # BA_DEF_ (signal/message attribute definitions)
    ba_def_pattern = r'BA_DEF_\s+[^;]+;'
    for match in re.finditer(ba_def_pattern, content):
        other_sections.append(match.group(0))

    # BA_ (signal/message attribute values)
    ba_pattern = r'BA_\s+[^;]+;'
    for match in re.finditer(ba_pattern, content):
        other_sections.append(match.group(0))

    # VAL_TABLE_ (value tables)
    val_table_pattern = r'VAL_TABLE_\s+[^;]+;'
    for match in re.finditer(val_table_pattern, content):
        other_sections.append(match.group(0))

    return {
        'version': version,
        'ns_section': ns_section,
        'bus_units': bus_units,
        'messages': messages,
        'value_definitions': value_definitions,
        'comments': comments,
        'other_sections': other_sections
    }

def analyze_conflicts(dbc_files):
    """Compare multiple DBC files and identify conflicts."""
    dbcs = {}
    message_sources = defaultdict(list)
    conflicts = []

    # Parse each DBC file
    for file_path in dbc_files:
        file_name = os.path.basename(file_path)
        parsed_dbc = parse_dbc_file(file_path)
        dbcs[file_path] = parsed_dbc

        # Track which files define which message IDs
        for msg_id in parsed_dbc['messages']:
            message_sources[msg_id].append(file_path)

    # Check for conflicts in message definitions
    for msg_id, sources in message_sources.items():
        if len(sources) > 1:
            # Multiple files define the same message ID
            messages = [dbcs[src]['messages'][msg_id] for src in sources]
            names = [msg['name'] for msg in messages]
            sizes = [msg['size'] for msg in messages]
            senders = [msg['sender'] for msg in messages]

            # Check if they have different names, sizes, or senders
            if len(set(names)) > 1 or len(set(sizes)) > 1 or len(set(senders)) > 1:
                conflict = {
                    'type': 'message',
                    'id': msg_id,
                    'sources': sources,
                    'names': names,
                    'sizes': sizes,
                    'senders': senders
                }
                conflicts.append(conflict)
                continue

            # Check for conflicts in signal definitions
            all_signals = set()
            for msg in messages:
                all_signals.update(msg['signals'].keys())

            for signal_name in all_signals:
                signal_defs = []
                for i, msg in enumerate(messages):
                    if signal_name in msg['signals']:
                        signal_defs.append((sources[i], msg['signals'][signal_name]))

                if len(signal_defs) > 1:
                    # Check if signal definitions are different
                    if not all(signal_defs[0][1] == signal_def[1] for signal_def in signal_defs[1:]):
                        conflict = {
                            'type': 'signal',
                            'message_id': msg_id,
                            'signal_name': signal_name,
                            'sources': [src for src, _ in signal_defs],
                            'definitions': [definition for _, definition in signal_defs]
                        }
                        conflicts.append(conflict)

    return conflicts, message_sources, dbcs

def print_conflicts(conflicts, dbc_priorities):
    """Print details about conflicts found and how they will be resolved."""
    print(f"Found {len(conflicts)} conflicts between files:")

    for i, conflict in enumerate(conflicts):
        print(f"\nConflict {i+1}:")
        if conflict['type'] == 'message':
            msg_id = conflict['id']
            print(f"  Message ID: {msg_id} (0x{msg_id:X})")
            for j, source in enumerate(conflict['sources']):
                print(f"  Source {j+1}: {os.path.basename(source)}")
                print(f"    Name: {conflict['names'][j]}")
                print(f"    Size: {conflict['sizes'][j]}")
                print(f"    Sender: {conflict['senders'][j]}")

            # Determine which source to use based on priority
            selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
            selected_index = conflict['sources'].index(selected_source)
            print(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} (priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})")
            print(f"    Selected: {conflict['names'][selected_index]} (size: {conflict['sizes'][selected_index]}, sender: {conflict['senders'][selected_index]})")

        elif conflict['type'] == 'signal':
            msg_id = conflict['message_id']
            signal = conflict['signal_name']
            print(f"  Signal: {signal} in message ID {msg_id} (0x{msg_id:X})")
            for j, source in enumerate(conflict['sources']):
                print(f"  Source {j+1}: {os.path.basename(source)}")
                def_str = ' '.join(str(x) for x in conflict['definitions'][j])
                print(f"    Definition: {def_str}")

            # Determine which source to use based on priority
            selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
            selected_index = conflict['sources'].index(selected_source)
            print(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} (priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})")
            def_str = ' '.join(str(x) for x in conflict['definitions'][selected_index])
            print(f"    Selected: {def_str}")

def resolve_conflict(sources, dbc_priorities):
    """Resolve conflict by selecting the source with highest priority."""
    # Convert source paths to basenames for comparison with priorities
    source_basenames = [os.path.basename(src) for src in sources]

    # Find the source with highest priority (lowest index in dbc_priorities)
    highest_priority_idx = float('inf')
    highest_priority_source = None

    for i, src in enumerate(sources):
        src_basename = os.path.basename(src)
        if src_basename in dbc_priorities:
            priority_idx = dbc_priorities.index(src_basename)
            if priority_idx < highest_priority_idx:
                highest_priority_idx = priority_idx
                highest_priority_source = src

    # If no match in priorities, use the first source
    if highest_priority_source is None:
        highest_priority_source = sources[0]

    return highest_priority_source

def auto_resolve_conflicts(conflicts, dbc_priorities):
    """Automatically resolve conflicts based on file priority."""
    decisions = {}

    for i, conflict in enumerate(conflicts):
        conflict_id = i + 1
        if conflict['type'] == 'message':
            sources = conflict['sources']
        else:  # signal conflict
            sources = conflict['sources']

        selected_source = resolve_conflict(sources, dbc_priorities)
        selected_index = sources.index(selected_source)
        decisions[conflict_id] = selected_index

    return decisions

def merge_dbc_files(dbc_files, output_file, conflicts, decisions, dbc_priorities):
    """Merge multiple DBC files using conflict resolution decisions."""
    # Re-analyze to get the latest data
    conflicts, message_sources, dbcs = analyze_conflicts(dbc_files)

    # Create a mapping of conflicts for easier lookup
    conflict_map = {}
    for i, conflict in enumerate(conflicts):
        if conflict['type'] == 'message':
            conflict_map[('message', conflict['id'])] = (i + 1, conflict)
        elif conflict['type'] == 'signal':
            conflict_map[('signal', conflict['message_id'], conflict['signal_name'])] = (i + 1, conflict)

    # Collect all unique bus units
    all_bus_units = set()
    for file_path, dbc in dbcs.items():
        all_bus_units.update(dbc['bus_units'])

    # Write merged DBC file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header and version
        f.write('CM_ "AUTOGENERATED MERGED FILE FROM MULTIPLE DBC FILES";\n\n')
        f.write('VERSION ""\n\n')

        # Write NS section from the first file
        first_file = list(dbcs.keys())[0]
        f.write('NS_ :\n')
        f.write(dbcs[first_file]['ns_section'])
        f.write('\n\nBS_:\n\n')

        # Write bus units
        f.write('BU_:')
        for unit in sorted(all_bus_units):
            if unit != 'XXX' and unit.strip():  # Skip generic XXX and empty units
                f.write(f' {unit}')
        f.write('\n\n\n')

        # Write value tables (from all files)
        val_tables = set()
        for dbc in dbcs.values():
            for section in dbc['other_sections']:
                if section.startswith('VAL_TABLE_'):
                    val_tables.add(section)

        for val_table in sorted(val_tables):
            f.write(f'{val_table}\n')

        if val_tables:
            f.write('\n')

        # Write message definitions
        written_messages = set()
        for msg_id, sources in sorted(message_sources.items()):
            if msg_id in written_messages:
                continue

            # Check if this message has a conflict
            conflict_key = ('message', msg_id)
            if conflict_key in conflict_map:
                conflict_id, conflict = conflict_map[conflict_key]

                # Use the decision to determine which source to use
                if conflict_id in decisions:
                    source_index = decisions[conflict_id]
                    if 0 <= source_index < len(sources):
                        source = sources[source_index]
                    else:
                        print(f"Warning: Invalid source index {source_index+1} for conflict {conflict_id}. Using first source.")
                        source = sources[0]
                else:
                    # No decision made, use the first source
                    print(f"Warning: No decision for conflict {conflict_id}. Using first source.")
                    source = sources[0]
            else:
                # No conflict, use the first source
                source = sources[0]

            msg = dbcs[source]['messages'][msg_id]

            # Extract the original message text but make sure it ends properly
            msg_text = msg['text'].strip()

            # Write the message definition
            f.write(f'{msg_text}\n\n')
            written_messages.add(msg_id)

        # Write other components from all files
        # Value definitions
        all_val_defs = set()
        for dbc in dbcs.values():
            all_val_defs.update(dbc['value_definitions'])

        for val_def in sorted(all_val_defs):
            f.write(f'{val_def}\n')

        if all_val_defs:
            f.write('\n')

        # BA_DEF_ and BA_ sections
        all_ba_defs = set()
        for dbc in dbcs.values():
            for section in dbc['other_sections']:
                if section.startswith('BA_DEF_') or section.startswith('BA_'):
                    all_ba_defs.add(section)

        for ba_def in sorted(all_ba_defs):
            f.write(f'{ba_def}\n')

        if all_ba_defs:
            f.write('\n')

        # Comments
        all_comments = set()
        for dbc in dbcs.values():
            all_comments.update(dbc['comments'])

        for comment in sorted(all_comments):
            f.write(f'{comment}\n')

        # Additional notes about the merge
        f.write('\n')
        for i, file_path in enumerate(dbc_files):
            file_name = os.path.basename(file_path)
            priority = dbc_priorities.index(file_name) + 1 if file_name in dbc_priorities else "N/A"
            f.write(f'CM_ "File {i+1}: {file_name} (Priority: {priority})";\n')

        # Add conflict resolution information
        f.write('\nCM_ "Conflict resolutions:";\n')
        for i, conflict in enumerate(conflicts):
            conflict_id = i + 1
            if conflict_id in decisions:
                source_index = decisions[conflict_id]
                if conflict['type'] == 'message':
                    msg_id = conflict['id']
                    selected_source = conflict['sources'][source_index]
                    selected_name = conflict['names'][source_index]
                    f.write(f'CM_ "Conflict {conflict_id}: Message ID {msg_id} (0x{msg_id:X}) - Used {os.path.basename(selected_source)} definition ({selected_name})";\n')
                else:  # signal conflict
                    msg_id = conflict['message_id']
                    signal = conflict['signal_name']
                    selected_source = conflict['sources'][source_index]
                    f.write(f'CM_ "Conflict {conflict_id}: Signal {signal} in message ID {msg_id} (0x{msg_id:X}) - Used {os.path.basename(selected_source)} definition";\n')

    print(f"Successfully merged {len(dbc_files)} DBC files into {output_file}")
    print(f"Total messages: {len(message_sources)}")
    print(f"Conflicts resolved: {len(decisions)}")
    return True

def extract_conflicts(conflicts, message_sources, dbc_priorities, output_file):
    """Extract and save conflicts to a separate file for review."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"CONFLICTS LIST FOR DBC MERGE\n")
        f.write(f"=============================\n\n")
        f.write(f"Found {len(conflicts)} conflicts across {len(message_sources)} unique message IDs.\n\n")
        f.write(f"Priority order (highest to lowest):\n")
        for i, dbc_file in enumerate(dbc_priorities):
            f.write(f"{i+1}. {dbc_file}\n")
        f.write("\n")

        for i, conflict in enumerate(conflicts):
            f.write(f"Conflict {i+1}:\n")
            if conflict['type'] == 'message':
                msg_id = conflict['id']
                f.write(f"  Message ID: {msg_id} (0x{msg_id:X})\n")
                for j, source in enumerate(conflict['sources']):
                    f.write(f"  Source {j+1}: {os.path.basename(source)}\n")
                    f.write(f"    Name: {conflict['names'][j]}\n")
                    f.write(f"    Size: {conflict['sizes'][j]}\n")
                    f.write(f"    Sender: {conflict['senders'][j]}\n")

                # Determine which source to use based on priority
                selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
                selected_index = conflict['sources'].index(selected_source)
                f.write(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} (priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})\n")
                f.write(f"    Selected: {conflict['names'][selected_index]} (size: {conflict['sizes'][selected_index]}, sender: {conflict['senders'][selected_index]})\n")

            elif conflict['type'] == 'signal':
                msg_id = conflict['message_id']
                signal = conflict['signal_name']
                f.write(f"  Signal: {signal} in message ID {msg_id} (0x{msg_id:X})\n")
                for j, source in enumerate(conflict['sources']):
                    f.write(f"  Source {j+1}: {os.path.basename(source)}\n")
                    def_str = ' '.join(str(x) for x in conflict['definitions'][j])
                    f.write(f"    Definition: {def_str}\n")

                # Determine which source to use based on priority
                selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
                selected_index = conflict['sources'].index(selected_source)
                f.write(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} (priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})\n")
                def_str = ' '.join(str(x) for x in conflict['definitions'][selected_index])
                f.write(f"    Selected: {def_str}\n")

            f.write("\n")

    print(f"Conflicts saved to: {output_file}")
    return True

if __name__ == "__main__":
    # Define the priority order for files (first has highest priority)
    dbc_priorities = [
        "hyundai_kia_mando_corner_radar_generated.dbc",
        "hyundai_kia_mando_front_radar_generated.dbc",
        "hyundai_canfd.dbc",
        "hyundai_kia_generic.dbc"
    ]

    dbc_files = [
        "opendbc/hyundai_canfd.dbc",
        "opendbc/hyundai_kia_mando_corner_radar_generated.dbc",
        "opendbc/hyundai_kia_mando_front_radar_generated.dbc",
        "opendbc/hyundai_kia_generic.dbc"
    ]

    output_file = "hyundai_kia_canfd_mando_radars.dbc"
    conflicts_output = f"{os.path.splitext(output_file)[0]}_CONFLICTS.txt"

    print("Analyzing DBC files...")
    for i, file_path in enumerate(dbc_files):
        try:
            dbc = parse_dbc_file(file_path)
            basename = os.path.basename(file_path)
            priority = dbc_priorities.index(basename) + 1 if basename in dbc_priorities else "N/A"
            print(f"{basename}: {len(dbc['messages'])} messages (Priority: {priority})")
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

    print("\nAnalyzing conflicts...")
    conflicts, message_sources, dbcs = analyze_conflicts(dbc_files)
    print(f"Found {len(conflicts)} conflicts across {len(message_sources)} unique message IDs.")

    # Print detailed conflict information and resolution
    print_conflicts(conflicts, dbc_priorities)

    # Extract conflicts to a separate file for review
    extract_conflicts(conflicts, message_sources, dbc_priorities, conflicts_output)

    # Automatically resolve conflicts based on file priority
    print("\nAutomatically resolving conflicts based on file priority...")
    decisions = auto_resolve_conflicts(conflicts, dbc_priorities)
    print(f"Resolved {len(decisions)} conflicts.")

    # Merge files using the decisions
    print("\nMerging files...")
    merge_dbc_files(dbc_files, output_file, conflicts, decisions, dbc_priorities)

    print(f"\nMerged file created: {output_file}")
    print("The merge prioritized files in this order:")
    for i, dbc_file in enumerate(dbc_priorities):
        print(f"{i+1}. {dbc_file}")

    print("\nUse this file with PlotJuggler to decode CAN signals from the vehicle.")