# Contributing to BLDC Motor PID Controller

Thank you for your interest in contributing to the BLDC Motor PID Controller project! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Documentation](#documentation)

## Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors. By participating, you agree to:

- Be respectful and inclusive
- Focus on constructive feedback
- Accept responsibility for mistakes
- Show empathy towards other contributors
- Help create a positive community

## How to Contribute

There are several ways you can contribute to this project:

### Types of Contributions

1. **Bug Reports**: Report bugs and issues
2. **Feature Requests**: Suggest new features or improvements
3. **Code Contributions**: Submit pull requests with fixes or enhancements
4. **Documentation**: Improve documentation, tutorials, or examples
5. **Testing**: Test the code and report issues or suggest test cases

### Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your changes
4. Make your changes following the guidelines below
5. Test your changes thoroughly
6. Submit a pull request

## Development Setup

### Prerequisites

- **Arduino IDE** (version 1.8.19 or later) or **Arduino CLI**
- **ESP32 board support** for Arduino (arduino-esp32 core)
- **Git** for version control

### Environment Setup

1. **Install Arduino IDE:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install arduino

   # Or download from https://www.arduino.cc/en/software
   ```

2. **Install ESP32 board support:**
   - Open Arduino IDE
   - Go to File → Preferences → Additional Boards Manager URLs
   - Add: `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
   - Tools → Board → Boards Manager → Search for "esp32" → Install

3. **Using Arduino CLI:**
   ```bash
   # Install Arduino CLI
   curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

   # Install cores
   arduino-cli core install esp32:esp32
   ```

### Building the Project

#### ESP32-C3 Bench Build
```bash
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
```

#### ESP32-C3 Production Build
```bash
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded
```

## Coding Standards

### C/C++ Style Guidelines

#### Naming Conventions
- **Variables**: `camelCase` (e.g., `pulseInterval`, `currentRPM`)
- **Functions**: `camelCase` (e.g., `calculateRPM()`, `readPotentiometer()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `CONTROL_LOOP_HZ`, `PID_OUTPUT_MAX`)
- **Types**: `PascalCase` for structs/classes (rare in Arduino)

#### Code Structure
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused on single responsibilities
- Use consistent indentation (2 or 4 spaces, match existing code)

#### Example Code Style
```c++
// Good: Clear naming and structure
volatile unsigned long pulseInterval = 0;
unsigned long lastRPMCalcTime = 0;

float calculateRPM() {
    // Atomic read to avoid race conditions
    noInterrupts();
    unsigned long interval = pulseInterval;
    interrupts();

    // Calculate RPM with proper units
    float rpm = (pulsesNow * 60000.0) / (timeDiff * PULSES_PER_REV);
    return rpm;
}

// Avoid: Unclear abbreviations or magic numbers
float calcRPM() {
    noInterrupts();
    unsigned long interval = pulseInterval;  // Clear variable name
    interrupts();

    return (p * 60000) / (t * 6);  // Magic numbers
}
```

### Arduino-Specific Guidelines

#### Pin Definitions
```c++
// Good: Clear pin purpose and mode
#define RPM_SENSOR_PIN      2   // Interrupt pin for BLDC Hall sensor
#define PWM_OUTPUT_PIN      9   // PWM output to ESC
#define MODE_SWITCH_PIN     3   // Digital input for mode selection

// Use INPUT_PULLUP for switches/sensors
pinMode(RPM_SENSOR_PIN, INPUT_PULLUP);
```

#### Memory Management
- Avoid large global arrays
- Minimize string usage in loops (especially inside the control task)

#### Interrupt Service Routines (ISRs)
- Keep ISRs short and fast
- Use volatile for shared variables
- Avoid function calls within ISRs
- Use atomic operations for multi-byte variables

### File Organization

```
PID_simple_controll/
├── esp32-c3/                    # ESP32-C3 implementation
│   ├── control/                # Bench build (serial console)
│   ├── embedded/               # Production build (enclosure)
│   ├── BUILDS.md               # Which build to use
│   ├── DIAGNOSTICS.md          # Console reference and fault isolation
│   └── README.md               # Implementation details
├── docs/                        # Guides (howto, troubleshooting, motor specs)
├── CONTRIBUTING.md             # This file
├── README.md                   # Project overview
└── LICENSE                     # License information
```

## Testing

### Unit Testing
- Test individual functions with known inputs/outputs
- Verify PID calculations with manual calculations
- Test edge cases (zero RPM, maximum RPM, etc.)

### Integration Testing
- Test complete motor control loop
- Verify serial commands work correctly
- Test EEPROM parameter storage/loading
- Validate PWM output characteristics

### Hardware Testing Checklist

#### Basic Functionality
- [ ] Power supply connections (5V, GND)
- [ ] Hall sensor wiring (any A/B/C wire to input pin)
- [ ] PWM output to ESC signal pin
- [ ] Common ground between all components

#### Motor Control Testing
- [ ] Motor spins at low RPM without load
- [ ] PID maintains target RPM under varying load
- [ ] Serial plotting shows stable control
- [ ] PID control stable (no oscillations)

#### Parameter Tuning
- [ ] Potentiometer mode changes parameters
- [ ] Serial commands adjust PID values
- [ ] EEPROM saves/loads parameters
- [ ] Period measurement provides accurate RPM at low speeds

#### Edge Cases
- [ ] Motor stall recovery
- [ ] Power interruption recovery
- [ ] Extreme temperature operation
- [ ] Electrical noise immunity

### Automated Testing
```bash
# Compile both builds
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded

# Check for compilation errors
echo "Compilation successful!"
```

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the coding standards
4. **Test thoroughly** - both compilation and hardware testing
5. **Update documentation** if needed
6. **Commit with clear messages**:
   ```bash
   git commit -m "feat: implement period measurement for RPM calculation

   - Replace pulse counting with period timing for better low-speed accuracy
   - Store in EEPROM for persistence
   - Add serial command SET PULSES <value>
   - Update documentation and help text

   Fixes #123"
   ```
7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Create a Pull Request** on GitHub

### Commit Message Guidelines

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Testing related changes
- `chore`: Maintenance tasks

Examples:
```
feat(pid): add anti-windup protection for integral term
fix(isr): prevent race conditions in period measurement
docs(readme): update PWM specification details
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Clear title** describing the issue
2. **Steps to reproduce** the problem
3. **Expected behavior** vs actual behavior
4. **Environment details**:
   - ESP32-C3 board and build used (`control/` or `embedded/`)
   - Motor and ESC model
   - Arduino IDE / arduino-cli version
   - Operating system
5. **Code snippets** if relevant
6. **Serial output** or error messages
7. **Hardware connections** diagram if possible

### Feature Requests

For feature requests, please include:

1. **Clear description** of the proposed feature
2. **Use case** - why is this feature needed?
3. **Implementation ideas** if you have any
4. **Impact assessment** - how does this affect existing functionality?

### Issue Templates

Use the following templates when creating issues:

#### Bug Report Template
```
## Bug Report

**Description:**
[Brief description of the bug]

**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Environment:**
- Board: [ESP32-C3 SuperMini]
- Build: [control/embedded]
- IDE Version: [1.8.x / 2.x / arduino-cli]
- OS: [Ubuntu 20.04/Windows 10]

**Additional Context:**
[Any other relevant information]
```

## Documentation

### Documentation Standards

- Use Markdown for all documentation files
- Keep README files in each implementation directory
- Include code examples where helpful
- Update documentation when code changes

### Documentation Files

- `README.md`: Project overview and getting started
- `esp32-c3/README.md`: ESP32-C3 implementation details
- `esp32-c3/BUILDS.md`: Which build to use, and how they share code
- `esp32-c3/DIAGNOSTICS.md`: Serial console commands and fault isolation
- `docs/howto.md`: Hardware assembly and setup guide
- `docs/mitigation.md`: Troubleshooting guide
- `CONTRIBUTING.md`: This file

### Updating Documentation

When making changes that affect documentation:

1. Update relevant README files
2. Add code comments for new functions
3. Update hardware schematics if pinouts change
4. Test documentation instructions on a fresh setup

---

Thank you for contributing to the BLDC Motor PID Controller project! Your contributions help make this a better tool for the embedded systems community.

For questions or discussions, please open an issue on GitHub.
