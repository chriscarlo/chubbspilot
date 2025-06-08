# Boot Sequence Transformation Roadmap

**Project:** Replace FrogPilot Boot Graphics with Chauffeur Terminal Interface  
**Status:** Planning Phase  
**Created:** January 8, 2025  
**Priority:** High - User Experience Enhancement  

## Executive Summary

This roadmap outlines the complete transformation of the openpilot boot sequence from the current FrogPilot graphics (static frog logo and animated spinner) to a professional, informative terminal-style interface featuring ASCII art branding and real-time system status updates.

## Current State Analysis

### Existing Boot Components
1. **Static Boot Logo** (`/usr/comma/bg.jpg`)
   - Displayed immediately at system boot via plymouth
   - Shows FrogPilot frog graphic during kernel initialization
   - No information about boot progress

2. **Qt Spinner Application** (`/selfdrive/ui/spinner`)
   - Animated comma logo with rotating track
   - Basic progress bar (0-100%)
   - Limited text display capability
   - Shows during device registration and service startup

### Boot Sequence Flow
1. System power on → Plymouth displays `/usr/comma/bg.jpg`
2. Kernel initialization and filesystem mounting
3. `launch_openpilot.sh` → `launch_chffrplus.sh`
4. `system/manager/manager.py` initialization
5. FrogPilot setup functions execute
6. Device registration (if needed) - spinner appears
7. Process startup sequence - progress updates
8. UI launch - boot complete

## Transformation Goals

### Primary Objectives
- Replace cartoon frog graphics with professional ASCII art branding
- Provide real-time boot status information
- Show actual system initialization progress
- Display hardware detection results
- Report service startup status
- Maintain 1980s mainframe aesthetic

### Design Principles
- **Informative**: Show what's actually happening during boot
- **Professional**: No cartoon characters or childish graphics  
- **Retro-Futuristic**: 1985 terminal aesthetic with modern functionality
- **Performant**: No boot time regression
- **Failsafe**: Graceful degradation if components fail

## Implementation Phases

### Phase 1: ASCII Art Logo Design & Generation (Week 1)

#### Tasks
1. **Logo Selection**
   - Finalize Chauffeur ASCII art design
   - Choose color scheme (red gradient on black)
   - Ensure readability at various resolutions

2. **PNG Generation Tool**
   - Create `tools/generate_boot_logo.py`
   - Support for different screen resolutions (720p, 1080p, 4K)
   - Anti-aliasing for smooth ASCII rendering
   - Scanline/CRT effect options

3. **Asset Creation**
   - Generate `chauffeur_boot_logo.png` at required resolutions
   - Create fallback monochrome version
   - Optimize file sizes for fast loading

#### Deliverables
- Final ASCII art logo design
- Logo generation script
- Boot logo PNG files
- Integration with FrogPilot setup

### Phase 2: Terminal Boot UI Development (Week 2-3)

#### Tasks
1. **Architecture Design**
   - Decide between Qt-based or native terminal approach
   - Design message passing for status updates
   - Plan graceful fallback mechanisms

2. **Core Implementation**
   - Create `/selfdrive/ui/terminal_boot/` module
   - Implement status tracking system
   - Build ASCII rendering engine
   - Add color support (ANSI escape codes)

3. **Status Integration**
   - Hook into manager.py for service status
   - Connect to hardware detection routines
   - Interface with network connectivity checks
   - Monitor resource usage (CPU/Memory)

#### Deliverables
- Terminal boot UI application
- Status tracking infrastructure
- Manager integration hooks
- Build system updates

### Phase 3: Information Display System (Week 3-4)

#### Tasks
1. **Status Categories**
   - Hardware detection (platform, serial, IMEI)
   - Network connectivity (WiFi, cellular, cloud)
   - Service startup (ordered by dependency)
   - Resource monitoring (CPU, memory, temperature)
   - Error reporting (with actionable messages)

2. **Visual Design**
   - Color coding: Green=[OK], Yellow=[WAIT], Red=[FAIL]
   - Progress indicators for long operations
   - Scrolling log for detailed output
   - Status summary dashboard

3. **Content Management**
   - Define status message formats
   - Create error message catalog
   - Design progress calculation logic
   - Implement ETA estimations

#### Deliverables
- Complete status display system
- Error message catalog
- Progress tracking algorithms
- Visual formatting templates

### Phase 4: Integration & Polish (Week 4-5)

#### Tasks
1. **System Integration**
   - Replace spinner invocations with terminal UI
   - Update FrogPilot functions for new assets
   - Modify manager.py boot sequence
   - Test on various hardware configurations

2. **Performance Optimization**
   - Profile boot time impact
   - Optimize rendering performance
   - Minimize memory usage
   - Implement lazy loading where appropriate

3. **Polish & Enhancement**
   - Add boot time statistics
   - Implement boot log persistence
   - Create diagnostic mode (verbose output)
   - Add customization options

#### Deliverables
- Fully integrated boot system
- Performance benchmarks
- Configuration options
- Documentation updates

### Phase 5: Testing & Rollout (Week 5-6)

#### Tasks
1. **Testing Matrix**
   - TICI device testing
   - PC development environment
   - Various screen resolutions
   - Network failure scenarios
   - Service startup failures

2. **User Acceptance**
   - Internal testing feedback
   - UI/UX refinements
   - Message clarity improvements
   - Timing adjustments

3. **Deployment**
   - Staged rollout plan
   - Rollback procedures
   - Monitoring strategy
   - User documentation

#### Deliverables
- Test results documentation
- Deployment procedures
- User guide
- Troubleshooting guide

## Technical Specifications

### File Structure
```
/selfdrive/ui/terminal_boot/
├── main.cc              # Entry point
├── terminal_ui.cc       # Main UI logic
├── terminal_ui.h        
├── status_tracker.cc    # Status management
├── status_tracker.h
├── ascii_renderer.cc    # ASCII art rendering
├── ascii_renderer.h
├── boot_messages.h      # Message definitions
└── SConscript          # Build configuration

/selfdrive/frogpilot/assets/boot/
├── chauffeur_boot_logo.png     # Generated boot logo
├── chauffeur_ascii_art.txt     # Source ASCII art
└── generate_logo.py            # Logo generation script
```

### Status Message Format
```
[COMPONENT] Description.................................................. [STATUS]
  └─ Detail line 1
  └─ Detail line 2
```

### Color Palette
- Background: #000000 (Pure Black)
- Primary Text: #FF0000 (Bright Red)
- Success: #00FF00 (Bright Green)
- Warning: #FFFF00 (Yellow)
- Error: #FF0000 (Red)
- Accent: #FF6B6B (Light Red)

### Example Boot Display
```
================================================================================
                         CHAUFFEUR BOOT SEQUENCE v2.0                           
================================================================================
[BOOT] Linux kernel 5.10.104...................................................... [OK]
[BOOT] Root filesystem mounted.................................................... [OK]
[BOOT] Hardware platform detected................................................. [OK]
  └─ Device: COMMA TICI (larch64)
  └─ Serial: CCF123456789
  └─ IMEI: 359876543210987

[INIT] System parameters loaded................................................... [OK]
[INIT] FrogPilot configuration.................................................... [OK]
[INIT] Network connectivity....................................................... [--]
  └─ WiFi: Not configured
  └─ Cellular: Searching for signal...
  └─ Status: Connecting to AT&T ████████░░░░░░░░ 50%

[PROC] Starting core services:
  ├─ thermald_manager......................................................... [OK]
  ├─ pandad................................................................... [OK]
  ├─ camerad.................................................................. [OK]
  ├─ modeld................................................................... [--]
  ├─ controlsd................................................................ [--]
  └─ ui....................................................................... [--]

[INFO] Boot time: 23.4s | CPU: 45% | Memory: 1.2GB/4GB | Temp: 42°C
================================================================================
```

## Success Metrics

### Quantitative
- Boot time: No regression (maintain < 30s)
- Memory usage: < 50MB for boot UI
- CPU usage: < 10% during display
- Error visibility: 100% of failures shown

### Qualitative
- Professional appearance
- Clear status communication
- Improved debugging capability
- Enhanced user confidence

## Risk Mitigation

### Technical Risks
- **Plymouth compatibility**: Test extensively, provide fallback
- **Performance impact**: Profile continuously, optimize aggressively
- **Hardware variations**: Test on all supported platforms
- **Resolution differences**: Design responsive layouts

### User Experience Risks
- **Information overload**: Balance detail with clarity
- **Boot time perception**: Ensure progress feels smooth
- **Error messaging**: Make failures actionable
- **Aesthetic preferences**: Provide customization options

## Future Enhancements

### Version 2.1
- Customizable color schemes
- Boot sound effects (optional)
- Network speed test display
- Storage health indicators

### Version 2.2
- Boot animation sequences
- Historical boot time graphs
- Diagnostic data export
- Remote boot monitoring

### Version 3.0
- Full TUI configuration interface
- Boot-time system checks
- Predictive failure warnings
- Integration with fleet management

## Conclusion

This roadmap transforms the openpilot boot experience from an uninformative cartoon display to a professional, informative system initialization interface. By providing real-time status updates and maintaining a cohesive retro-futuristic aesthetic, we enhance both the user experience and system diagnostics capabilities while eliminating the "what's that frog doing?" confusion entirely.

The phased approach ensures manageable implementation milestones while maintaining system stability throughout the transformation process.