# Cross-Platform Testing Plan

## Goal
Enable comprehensive testing of FrogPilot features on x86_64 development machines while ensuring compatibility with aarch64 TICI runtime environment.

## Testing Strategy Layers

### 1. Build-Time Verification
- **Cross-compilation checks**: Verify code compiles for aarch64
- **Static analysis**: Architecture-independent code analysis
- **Type checking**: MyPy validation across platforms
- **Dependency validation**: Ensure all dependencies available on TICI

### 2. Unit Testing (Platform-Independent)
- Pure Python code: Run directly on development machine
- C++ components: Compile and test with architecture stubs
- Algorithm testing: Verify logic without hardware dependencies
- Data processing: Test with recorded/synthetic data

### 3. Integration Testing (With Mocks)
- **Hardware Abstraction Layer (HAL) Mocks**
  - Camera interface mocks
  - CAN bus simulation
  - Sensor data replay
  - Power management stubs
- **Process Communication Testing**
  - Message passing verification
  - Service interaction testing
  - State machine validation

### 4. Simulation Testing
- **MetaDrive Integration**
  - Driving scenario testing
  - Model inference validation
  - Control algorithm verification
- **Replay Testing**
  - Use recorded drives for regression testing
  - Validate processing pipeline
  - Performance benchmarking

### 5. Remote Device Testing
- **SSH-based Testing**
  - Deploy and run tests on connected TICI
  - Real-time log streaming
  - Performance monitoring
- **CI/CD Integration**
  - Automated testing on device pool
  - Parallel test execution
  - Result aggregation

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up cross-compilation environment
- [ ] Create HAL mock framework
- [ ] Implement basic build verification
- [ ] Document setup process

### Phase 2: Core Testing (Week 3-4)
- [ ] Expand unit test coverage
- [ ] Implement CAN bus simulation
- [ ] Create sensor data mocks
- [ ] Set up replay testing framework

### Phase 3: Integration (Week 5-6)
- [ ] Remote device testing automation
- [ ] CI/CD pipeline enhancement
- [ ] Performance benchmarking tools
- [ ] Test result dashboard

### Phase 4: Advanced Features (Week 7-8)
- [ ] Hardware-specific feature testing
- [ ] Edge case simulation
- [ ] Stress testing framework
- [ ] Documentation and training

## Testing Environments

### 1. Local Development
```bash
# Build for x86_64 with mocks
scons -j8 --test-mode

# Run unit tests
pytest -n auto

# Run with simulation
python tools/sim/launch_sim.py
```

### 2. Cross-Compilation
```bash
# Build for aarch64
scons -j8 --arch=aarch64

# Verify build artifacts
tools/verify_build.py --arch=aarch64
```

### 3. Remote Testing
```bash
# Deploy to device
tools/deploy_to_device.py --device=<IP>

# Run tests remotely
tools/remote_test.py --device=<IP> --suite=integration
```

### 4. CI/CD Pipeline
```yaml
# Jenkins pipeline stages
- Build x86_64
- Build aarch64
- Unit Tests
- Simulation Tests
- Device Tests (parallel)
- Performance Tests
```

## Key Components to Mock/Simulate

### Hardware Interfaces
1. **Cameras** (road, driver, wide)
   - Video stream simulation
   - Frame timing accuracy
   - Multiple camera synchronization

2. **CAN Bus**
   - Message generation
   - Timing simulation
   - Error injection

3. **Sensors**
   - IMU data generation
   - GPS simulation
   - Temperature sensors

4. **Platform-Specific**
   - Power management
   - Hardware acceleration (GPU/DSP)
   - Memory constraints

### Software Components
1. **AGNOS Services**
   - System services
   - Hardware management
   - Boot process

2. **Model Inference**
   - SNPE runtime simulation
   - ONNX runtime compatibility
   - Performance characteristics

3. **Real-time Constraints**
   - Timing simulation
   - Priority management
   - Resource allocation

## Success Metrics

1. **Build Success Rate**: >95% of commits build for both architectures
2. **Test Coverage**: >80% code coverage on development machine
3. **Device Parity**: <5% difference in test results between simulation and device
4. **Performance**: Simulation within 2x of device performance
5. **Developer Velocity**: <30 minutes from code change to tested on device

## Tools and Scripts Needed

1. **Build Tools**
   - Cross-compilation setup script
   - Build verification tool
   - Architecture compatibility checker

2. **Testing Tools**
   - Mock generation framework
   - Data replay system
   - Performance profiler

3. **Deployment Tools**
   - Remote deployment script
   - Log aggregation system
   - Test orchestration framework

4. **Analysis Tools**
   - Test result analyzer
   - Performance comparison tool
   - Coverage reporter