import re
import os
from collections import defaultdict

def parse_dbc_file(file_path):
    """
    Parse a DBC file in a line-based way:
      - Read the file line by line.
      - Capture each message (BO_) along with its SG_ lines, etc. in a 'lines' list.
      - Also separately capture VAL_, BA_, CM_, VAL_TABLE_, etc. lines in sets/lists.

    This preserves original newlines (so we can re-output messages in a readable format).
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        all_lines = f.readlines()

    # Extract version (just one-liner if present)
    version = ""
    version_regex = re.compile(r'^VERSION\s+"([^"]*)"\s*$')

    # We'll collect everything else in these structures:
    ns_section_lines = []
    bus_units = []

    # For messages, store as:
    #   messages[msg_id] = {
    #       'id': msg_id,
    #       'name': <string>,
    #       'size': <int>,
    #       'sender': <string>,
    #       'lines': [str, str, ... all lines for that message],
    #       'signals': dict of signals parsed out
    #   }
    messages = {}

    # For deduplicating attributes, values, comments, etc., keep them as lines
    # but we store them in sets so we don't get duplicates across files
    # (If you want to keep duplicates verbatim, you could use lists instead.)
    value_definitions = set()  # lines with VAL_ ...
    comments = set()           # lines with CM_ ...
    other_sections = set()     # lines with BA_, BA_DEF_, VAL_TABLE_, etc.

    # We'll do a quick pass to capture the "BUS UNITS" line if it appears
    # (BU_: <units>).
    # Similarly, the NS_ and BS_ sections are just lines until we hit "BU_:" or "BO_:" or end.
    # For practical reasons, we’ll do it with a small state machine approach.

    # For capturing lines belonging to the "NS_ :" section (until we see BS_:)
    # or the BU_: line. This is simpler than big regex for those sections.

    # State machine:
    #   "GLOBAL"  -> reading lines at top level
    #   "INSIDE_MESSAGE" -> we have encountered a BO_ line, collecting lines until next BO_ or end
    current_message_id = None
    current_message_lines = []
    current_message_signals = {}
    current_state = "GLOBAL"

    bo_regex = re.compile(r'^BO_\s+(\d+)\s+([^:]+):\s+(\d+)\s+(\S.*)$')
    sg_regex = re.compile(r'^\s*SG_\s+([^\s:]+)\s*:\s*([^"]+)"([^"]*)"(.*)')

    # Helper to finalize a message we were collecting
    def finalize_message():
        if current_message_id is not None and current_message_lines:
            # Parse out fields from the first line (BO_...) again
            first_line = current_message_lines[0].rstrip('\n')
            m = bo_regex.match(first_line)
            if m:
                msg_id_str, msg_name, msg_size_str, msg_sender = m.groups()
                msg_id = int(msg_id_str)
                msg_size = int(msg_size_str)
                messages[msg_id] = {
                    'id': msg_id,
                    'name': msg_name.strip(),
                    'size': msg_size,
                    'sender': msg_sender.strip(),
                    'lines': current_message_lines[:],  # copy of the list
                    'signals': dict(current_message_signals)
                }

    for line in all_lines:
        line_stripped = line.strip('\r\n')

        # Check for version line
        version_match = version_regex.match(line_stripped)
        if version_match:
            version = version_match.group(1)

        # If we’re not inside a message block, see if this line starts a new message
        if current_state == "GLOBAL":
            # Check if line starts a new BO_ message
            bo_match = bo_regex.match(line_stripped)
            if bo_match:
                # Start a new message block
                current_state = "INSIDE_MESSAGE"
                current_message_id = int(bo_match.group(1))
                current_message_lines = [line]
                current_message_signals = {}
                continue

            # If line is BU_: <units...> store it
            if line_stripped.startswith('BU_:'):
                # parse out units
                # e.g. "BU_: XXX CAMERA FRONT_RADAR ADRV APRK"
                # separate by whitespace after "BU_:"
                parted = line_stripped.split(':', 1)
                if len(parted) == 2:
                    raw_units = parted[1].strip()
                    bus_units.extend(raw_units.split())

            # If line starts with "NS_ :" or "BS_:", just store them in memory
            # We'll add them to final output from the first file later
            # For simplicity, let’s store them all in ns_section_lines, we can do a simple parse
            if line_stripped.startswith('NS_ :'):
                ns_section_lines.append(line)
                continue
            elif line_stripped.startswith('BS_:'):
                ns_section_lines.append(line)
                continue

            # Check for attribute lines, value lines, comment lines, etc.
            # We'll store them in sets for dedup. (If you want to preserve order, use lists.)
            if line_stripped.startswith('VAL_ '):
                value_definitions.add(line)
                continue
            elif line_stripped.startswith('CM_ '):
                comments.add(line)
                continue
            elif line_stripped.startswith('BA_DEF_') or line_stripped.startswith('BA_'):
                other_sections.add(line)
                continue
            elif line_stripped.startswith('VAL_TABLE_'):
                other_sections.add(line)
                continue

            # Otherwise, store or ignore. Possibly it’s part of the NS section, or random lines
            ns_section_lines.append(line)

        elif current_state == "INSIDE_MESSAGE":
            # We’re reading lines for the current message
            bo_match = bo_regex.match(line_stripped)
            if bo_match:
                # We have encountered a new BO_ => finalize the old message and start a new one
                finalize_message()
                current_message_id = int(bo_match.group(1))
                current_message_lines = [line]
                current_message_signals = {}
                continue
            else:
                # Add this line to current message
                current_message_lines.append(line)

                # If it is an SG_ line, parse out signal def
                sg_match = sg_regex.match(line_stripped)
                if sg_match:
                    sg_name = sg_match.group(1).strip()
                    sg_def = sg_match.group(2).strip()
                    sg_unit = sg_match.group(3).strip()
                    sg_receivers = sg_match.group(4).strip()
                    current_message_signals[sg_name] = (sg_def, sg_unit, sg_receivers)

    # If we ended the file while still inside a message, finalize that last message
    if current_state == "INSIDE_MESSAGE":
        finalize_message()

    # Convert bus_units to a list of unique items
    bus_units = list(dict.fromkeys(bus_units))  # preserve order but remove duplicates

    return {
        'version': version,
        'ns_section_lines': ns_section_lines,  # raw lines for NS_ and BS_ or any leftover
        'bus_units': bus_units,
        'messages': messages,
        'value_definitions': value_definitions,
        'comments': comments,
        'other_sections': other_sections
    }


def analyze_conflicts(dbc_files):
    """
    Compare multiple DBC files and identify conflicts in messages/signals.
    This part is largely the same as in your original script.
    """
    dbcs = {}
    message_sources = defaultdict(list)
    conflicts = []

    # Parse each DBC
    for file_path in dbc_files:
        parsed = parse_dbc_file(file_path)
        dbcs[file_path] = parsed

        # Track which files define which message IDs
        for msg_id in parsed['messages']:
            message_sources[msg_id].append(file_path)

    # Check conflicts
    for msg_id, sources in message_sources.items():
        if len(sources) > 1:
            # same message ID in multiple files
            messages = [dbcs[src]['messages'][msg_id] for src in sources]
            names = [m['name'] for m in messages]
            sizes = [m['size'] for m in messages]
            senders = [m['sender'] for m in messages]

            # If they differ in name, size, or sender => conflict
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

            # Check signals
            all_signals = set()
            for msg in messages:
                all_signals.update(msg['signals'].keys())

            for signal_name in all_signals:
                signal_defs = []
                for i, msg in enumerate(messages):
                    if signal_name in msg['signals']:
                        signal_defs.append((sources[i], msg['signals'][signal_name]))

                if len(signal_defs) > 1:
                    # If definitions differ
                    first_def = signal_defs[0][1]
                    for (_, other_def) in signal_defs[1:]:
                        if other_def != first_def:
                            conflict = {
                                'type': 'signal',
                                'message_id': msg_id,
                                'signal_name': signal_name,
                                'sources': [s for s, _ in signal_defs],
                                'definitions': [d for _, d in signal_defs]
                            }
                            conflicts.append(conflict)
                            break

    return conflicts, message_sources, dbcs


def print_conflicts(conflicts, dbc_priorities):
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
            selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
            selected_index = conflict['sources'].index(selected_source)
            print(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} "
                  f"(priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})")
        elif conflict['type'] == 'signal':
            msg_id = conflict['message_id']
            signal = conflict['signal_name']
            print(f"  Signal: {signal} in message ID {msg_id} (0x{msg_id:X})")
            for j, source in enumerate(conflict['sources']):
                print(f"  Source {j+1}: {os.path.basename(source)}")
                def_str = ' '.join(str(x) for x in conflict['definitions'][j])
                print(f"    Definition: {def_str}")
            selected_source = resolve_conflict(conflict['sources'], dbc_priorities)
            selected_index = conflict['sources'].index(selected_source)
            print(f"  RESOLUTION: Using definition from {os.path.basename(selected_source)} "
                  f"(priority {dbc_priorities.index(os.path.basename(selected_source)) + 1})")


def resolve_conflict(sources, dbc_priorities):
    # same as before
    highest_priority_idx = float('inf')
    highest_priority_source = None
    for src in sources:
        basename = os.path.basename(src)
        if basename in dbc_priorities:
            idx = dbc_priorities.index(basename)
            if idx < highest_priority_idx:
                highest_priority_idx = idx
                highest_priority_source = src
    if highest_priority_source is None:
        return sources[0]
    return highest_priority_source


def auto_resolve_conflicts(conflicts, dbc_priorities):
    decisions = {}
    for i, conflict in enumerate(conflicts):
        conflict_id = i + 1
        selected = resolve_conflict(conflict['sources'], dbc_priorities)
        selected_index = conflict['sources'].index(selected)
        decisions[conflict_id] = selected_index
    return decisions


def merge_dbc_files(dbc_files, output_file, conflicts, decisions, dbc_priorities):
    # re-analyze
    conflicts, message_sources, dbcs = analyze_conflicts(dbc_files)

    # map conflicts
    conflict_map = {}
    for i, conflict in enumerate(conflicts):
        c_id = i + 1
        if conflict['type'] == 'message':
            conflict_map[('message', conflict['id'])] = (c_id, conflict)
        else:  # signal conflict
            conflict_map[('signal', conflict['message_id'], conflict['signal_name'])] = (c_id, conflict)

    # gather all bus units
    all_bus_units = set()
    for path, dbc in dbcs.items():
        all_bus_units.update(dbc['bus_units'])

    # gather sets of other lines
    all_val_defs = set()
    all_comments = set()
    all_other_sections = set()

    for path, dbc in dbcs.items():
        all_val_defs.update(dbc['value_definitions'])
        all_comments.update(dbc['comments'])
        all_other_sections.update(dbc['other_sections'])

    # We'll use the FIRST file's NS_ lines + version as a base
    first_file = dbc_files[0]
    version = dbcs[first_file]['version']
    ns_section_lines = dbcs[first_file]['ns_section_lines']

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write a header
        f.write('CM_ "AUTOGENERATED MERGED FILE FROM MULTIPLE DBC FILES";\n\n')
        f.write(f'VERSION "{version}"\n\n' if version else 'VERSION ""\n\n')

        # Write NS_ lines (including BS_) we captured from the first file
        for ln in ns_section_lines:
            f.write(ln if ln.endswith('\n') else ln + '\n')
        f.write('\n')

        # Write bus units
        f.write('BU_:')
        for unit in sorted(all_bus_units):
            if unit.strip() and unit != 'XXX':
                f.write(f' {unit}')
        f.write('\n\n')

        # Now, we sort messages by ID so it’s consistent
        all_msg_ids = sorted(message_sources.keys())

        written_messages = set()
        for msg_id in all_msg_ids:
            # check conflict
            c_key = ('message', msg_id)
            if c_key in conflict_map:
                c_id, conflict = conflict_map[c_key]
                if c_id in decisions:
                    src_index = decisions[c_id]
                    chosen_file = conflict['sources'][src_index]
                else:
                    # fallback
                    chosen_file = conflict['sources'][0]
            else:
                # no conflict
                chosen_file = message_sources[msg_id][0]

            # Write out the chosen file’s lines for that message
            chosen_msg = dbcs[chosen_file]['messages'][msg_id]
            for ln in chosen_msg['lines']:
                if not ln.endswith('\n'):
                    f.write(ln + '\n')
                else:
                    f.write(ln)
            f.write('\n')
            written_messages.add(msg_id)

        # Write out value definitions
        if all_val_defs:
            for ln in sorted(all_val_defs):
                if not ln.endswith('\n'):
                    f.write(ln + '\n')
                else:
                    f.write(ln)
            f.write('\n')

        # Write out BA_ and BA_DEF_ sections, VAL_TABLE_ lines, etc.
        if all_other_sections:
            for ln in sorted(all_other_sections):
                if not ln.endswith('\n'):
                    f.write(ln + '\n')
                else:
                    f.write(ln)
            f.write('\n')

        # Write out comments
        if all_comments:
            for ln in sorted(all_comments):
                if not ln.endswith('\n'):
                    f.write(ln + '\n')
                else:
                    f.write(ln)
            f.write('\n')

        # Final notes
        for i, path in enumerate(dbc_files):
            base = os.path.basename(path)
            prio = dbc_priorities.index(base) + 1 if base in dbc_priorities else 'N/A'
            f.write(f'CM_ "File {i+1}: {base} (Priority: {prio})";\n')
        f.write('\nCM_ "Conflict resolutions:";\n')
        for i, conflict in enumerate(conflicts):
            c_id = i + 1
            if c_id in decisions:
                src_idx = decisions[c_id]
                if conflict['type'] == 'message':
                    msg_id = conflict['id']
                    chosen_src = conflict['sources'][src_idx]
                    chosen_name = conflict['names'][src_idx]
                    f.write(f'CM_ "Conflict {c_id}: Message ID {msg_id} - Using {os.path.basename(chosen_src)} ({chosen_name})";\n')
                else:
                    msg_id = conflict['message_id']
                    sig = conflict['signal_name']
                    chosen_src = conflict['sources'][src_idx]
                    f.write(f'CM_ "Conflict {c_id}: Signal {sig} in Msg ID {msg_id} - Using {os.path.basename(chosen_src)}";\n')

    print(f"\nSuccessfully merged {len(dbc_files)} DBC files into {output_file}")
    print(f"Total messages: {len(message_sources)}")
    print(f"Conflicts resolved: {len(decisions)}")
    return True


if __name__ == "__main__":
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

    print("Analyzing DBC files...")
    for fp in dbc_files:
        try:
            parsed = parse_dbc_file(fp)
            base = os.path.basename(fp)
            prio = dbc_priorities.index(base) + 1 if base in dbc_priorities else 'N/A'
            print(f"{base}: {len(parsed['messages'])} messages (Priority: {prio})")
        except Exception as e:
            print(f"Error parsing {fp}: {e}")

    print("\nAnalyzing conflicts...")
    conflicts, msg_sources, dbcs = analyze_conflicts(dbc_files)
    print(f"Found {len(conflicts)} conflicts across {len(msg_sources)} unique message IDs.")

    # Print conflicts
    print_conflicts(conflicts, dbc_priorities)

    # Auto resolve
    print("\nAutomatically resolving conflicts based on priority...")
    decisions = auto_resolve_conflicts(conflicts, dbc_priorities)
    print(f"Resolved {len(decisions)} conflicts.")

    # Merge
    print("\nMerging files...")
    merge_dbc_files(dbc_files, output_file, conflicts, decisions, dbc_priorities)

    print(f"\nMerged file created: {output_file}")
    print("Priority order used:")
    for i, f in enumerate(dbc_priorities):
        print(f"{i+1}. {f}")
