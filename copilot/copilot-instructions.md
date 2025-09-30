# Lanvan Copilot Instructions

## 📋 Project Overview

**Lanvan** is a LAN-based file transfer application built with FastAPI that enables secure, high-performance file sharing across devices on local networks. It features real-time streaming uploads, AES encryption, and cross-platform compatibility including Android Termux.

### Core Capabilities
- **Real-time streaming file transfers** with chunked upload optimization
- **AES-256 encryption** for secure transfers over HTTP/HTTPS
- **Cross-platform support** including Windows, Linux, macOS, and Android Termux
- **mDNS service discovery** for automatic network detection
- **WebSocket-based real-time updates** and clipboard synchronization
- **Concurrent upload management** with adaptive performance optimization

## 🛠️ Tech Stack

### Backend
- **FastAPI** (0.104.1) - Modern async web framework
- **Uvicorn** - ASGI server with WebSocket support
- **Jinja2** - Template engine for dynamic HTML
- **Cryptography** (41.0.7) - AES encryption implementation
- **PSUtil** - System monitoring and resource management
- **ZeroConf** - mDNS service discovery for local network detection
- **AIOFiles** - Async file operations

### Frontend
- **Vanilla JavaScript** - No frameworks, optimized for performance
- **WebSockets** - Real-time communication with server
- **File API** - Modern browser file handling
- **CSS Grid/Flexbox** - Responsive layout design

### Testing & Tools
- **Custom test suite** - Comprehensive testing in `testing/test_workspace/tests/`
- **qt.py** - Quick testing and validation tool
- **Performance monitoring** - Built-in streaming assembly verification

## 📁 Project Structure

```
Lanvan/
├── run.py                 # Main application entry point
├── qt.py                  # Quick testing tool
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
├── p2p partial.md        # P2P implementation specification
├── app/                  # Core application code
│   ├── main.py           # FastAPI application setup
│   ├── routes.py         # API endpoints and file handling
│   ├── config.py         # Configuration management
│   ├── aes_config.py     # AES encryption configuration
│   ├── performance_config.py # Performance optimization settings
│   ├── simple_mdns.py    # mDNS service discovery
│   ├── streaming_assembly.py # Real-time file assembly
│   ├── templates/        # Jinja2 HTML templates
│   │   └── index.html    # Main UI template
│   └── static/           # Static assets
│       ├── css/          # Stylesheets
│       └── js/           # JavaScript modules
│           └── file-utils.js # Core frontend utilities
├── docs/                 # Documentation
│   └── TERMUX_SETUP.md   # Android/Termux setup guide
├── testing/              # Test infrastructure
│   └── test_workspace/tests/ # Comprehensive test suite
├── utils/                # Utility scripts
│   ├── fast_boot.py      # Quick startup utilities
│   ├── quick_start.py    # Simplified startup
│   └── system_verification.py # System validation
├── scanners/             # Code analysis tools
├── certs/                # SSL certificate management
└── archive/              # Archived/legacy code
```

## 🎯 Development Guidelines

### Code Style & Patterns
1. **Python**: Follow PEP 8, use type hints, async/await for I/O operations
2. **JavaScript**: ES6+ features, avoid external dependencies, use semantic variable names
3. **HTML/CSS**: Semantic markup, CSS Grid/Flexbox, responsive design
4. **Error Handling**: Comprehensive try/catch blocks, graceful degradation
5. **Performance**: Prioritize streaming operations, minimal memory usage

### 🚨 **CRITICAL DEVELOPMENT RULES**
1. **No Inline Code**: Never use inline JavaScript or CSS in HTML templates
2. **External Files Only**: Always create separate `.js` and `.css` files for new functionality
3. **Check Existing Files First**: Before creating new files, check if functionality can be added to existing files:
   - **JavaScript**: Use `app/static/js/file-utils.js` for utility functions
   - **CSS**: Use `app/static/css/style.css` or `app/static/css/main-styles.css`
4. **Modular Design**: Write reusable, modular code that can be easily maintained
5. **File Reuse**: Always extend existing files rather than creating duplicates

### Modular Code Organization
- **JavaScript Functions**: Add to `file-utils.js` with clear function names
- **CSS Styles**: Group related styles in logical sections within existing CSS files
- **HTML Templates**: Keep templates clean with external references only
- **Configuration**: Use existing config files (`config.py`, `aes_config.py`, etc.)

### Key Architecture Principles
- **Async-first**: All I/O operations use async/await
- **Streaming-based**: Real-time file assembly, no temporary storage
- **Server-based**: Centralized file transfer with WebSocket communication
- **Cross-platform**: Code must work on Windows, Linux, macOS, Android Termux
- **Local network focused**: Optimized for LAN environments with mDNS discovery

### 🌐 **CRITICAL COMPATIBILITY REQUIREMENTS**

#### **Offline-First Design** 📶
- **No Internet Dependencies**: All features must work without internet connectivity
- **Local Resource Usage**: Use local libraries, no CDN dependencies
- **Cached Assets**: Store all required assets locally
- **Graceful Degradation**: Features should work even when external services are unavailable

#### **Termux Compatibility** 📱
- **Android Environment**: Code must work in Android Termux environment
- **Memory Constraints**: Consider limited memory on mobile devices
- **File System Access**: Use proper file paths compatible with Termux
- **Network Limitations**: Handle Android network restrictions gracefully
- **Battery Optimization**: Minimize CPU usage for better battery life

#### **Universal Viability** 🌍
- **Multiple Platforms**: Windows, Linux, macOS, Android Termux
- **Various Network Conditions**: WiFi, cellular, limited bandwidth
- **Different Hardware**: Desktop, mobile, low-end devices
- **Browser Compatibility**: Modern browsers without requiring specific features

#### **Implementation Strategy** 🎯
When implementing features, **ALWAYS**:
1. **Assess Compatibility Impact**: How does this affect offline/Termux usage?
2. **Test Across Platforms**: Verify on desktop and Android/Termux
3. **Provide Fallbacks**: Include alternative approaches for constrained environments
4. **Document Limitations**: Note any platform-specific considerations
5. **Offer Path Options**: Present multiple implementation approaches when needed

### Security Considerations
- **AES-256 encryption** for all file transfers over HTTP
- **HTTPS support** with automatic certificate generation
- **Input validation** on all user inputs and file uploads
- **Memory safety** - proper cleanup of sensitive data
- **XSS protection** in HTML templates

## 🔧 Development Environment

### Setup Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py

# Quick testing
python qt.py

# Android/Termux testing
python qt.py --android
```

### Build & Test Workflow
1. **Code changes**: Run `python qt.py` to verify server starts
2. **Feature validation**: Run specific tests in `testing/test_workspace/tests/`
3. **Performance testing**: Use `test_streaming_complete.py`
4. **Cross-platform**: Test on desktop and mobile browsers
5. **Integration**: Verify all components work together

### Important Files to Understand
- **`app/main.py`**: Application initialization, middleware, CORS
- **`app/routes.py`**: All API endpoints, file upload/download logic
- **`app/streaming_assembly.py`**: Core streaming file assembly engine
- **`app/static/js/file-utils.js`**: Frontend utility functions
- **`app/templates/index.html`**: Main UI with WebSocket integration

## ⚠️ Critical Notes & Workarounds

### Known Considerations
- **Memory Management**: Large files use streaming assembly to avoid memory issues
- **Termux Compatibility**: Special handling for Android environment limitations
- **Port Binding**: Automatic fallback from port 80/443 to 5000/5001 for non-root users
- **Debug Mode**: Use `DEBUG_MODE = True` in file-utils.js for development
- **Chunked Uploads**: Files >250MB automatically use chunked transfer

### Performance Optimizations
- **Concurrent uploads**: Adaptive concurrency based on network speed
- **Chunk size adaptation**: Dynamic adjustment based on device capabilities
- **Memory cleanup**: Automatic garbage collection for long-running sessions
- **Network detection**: Smart fallback strategies for different connection types
- **Streaming assembly**: Real-time file assembly without temporary storage

## 🚀 Common Tasks

### Adding New Features - **FOLLOW THESE STEPS EXACTLY**

#### 1. **Check Existing Files First** 🔍
- **JavaScript**: Check if functionality exists in `app/static/js/file-utils.js`
- **CSS**: Check `app/static/css/style.css` and `app/static/css/main-styles.css`
- **Backend**: Review `app/routes.py` for similar endpoints
- **Config**: Check existing config files before creating new ones

#### 2. **Development Process** 📝
1. **Backend**: Add routes in `app/routes.py`, update `app/main.py` if needed
2. **Frontend JavaScript**: 
   - **ALWAYS** add functions to existing `app/static/js/file-utils.js`
   - **NEVER** use inline JavaScript in HTML
   - Write modular, reusable functions
3. **Frontend CSS**:
   - **ALWAYS** add styles to existing CSS files
   - **NEVER** use inline styles in HTML
   - Group related styles logically
4. **UI**: Update `app/templates/index.html` with **external references only**
5. **Testing**: Create test in `testing/test_workspace/tests/`

#### 3. **File Organization Rules** 📂
- **Extend, Don't Create**: Always try to extend existing files first
- **Modular Functions**: Write small, focused, reusable functions
- **Clear Naming**: Use descriptive function and variable names
- **Documentation**: Add comments explaining complex functionality

### Debugging Issues
1. **Server errors**: Check uvicorn logs, use `python qt.py` for quick validation
2. **Frontend issues**: Enable debug mode in file-utils.js
3. **Performance problems**: Use streaming assembly tests
4. **Cross-platform**: Test with Android/Termux using `qt.py --android`
5. **CSS/JS Issues**: Verify external files are properly linked in HTML templates

### Performance Tuning
- **Upload speed**: Adjust chunk sizes in performance_config.py
- **Concurrency**: Modify concurrent upload limits
- **Memory usage**: Check streaming assembly configuration
- **Network optimization**: Tune timeout and retry settings

## 🚨 **DEVELOPMENT VIOLATIONS TO AVOID**

### ❌ **Never Do These:**
1. **Inline JavaScript**: `<script>function myFunc(){}</script>` in HTML
2. **Inline CSS**: `<div style="color: red;">` in HTML templates
3. **Duplicate Files**: Creating new JS/CSS files when existing ones can be extended
4. **Monolithic Functions**: Writing large, single-purpose functions
5. **Hardcoded Values**: Put configuration in appropriate config files

### ✅ **Always Do These:**
1. **External References**: `<script src="path/to/file.js"></script>`
2. **Modular Design**: Small, reusable functions in existing files
3. **File Reuse**: Extend `file-utils.js` and existing CSS files
4. **Clean Templates**: HTML templates with external references only
5. **Configuration Management**: Use existing config files for settings

## 🔍 **MANDATORY PROJECT SCANNING PROTOCOL**

### **Before Starting Major Work** 📊
**ALWAYS perform comprehensive project analysis before implementing major features:**

#### 1. **Codebase Inventory** 🗃️
```bash
# Use these tools to scan the project:
semantic_search("relevant functionality keywords")
grep_search("function names, patterns")
file_search("*.js *.css *.py")
```

#### 2. **Analysis Requirements** 📋
- **Existing Functionality**: Check if similar features already exist
- **Code Patterns**: Identify established patterns and conventions  
- **File Structure**: Map current organization and dependencies
- **Integration Points**: Find where new code should connect
- **Performance Impact**: Assess how changes affect existing systems
- **Compatibility Check**: Verify offline and Termux compatibility requirements

#### 3. **Work Planning Based on Findings** 🎯
- **Reuse First**: Extend existing code when possible
- **Pattern Matching**: Follow established code patterns
- **Integration Strategy**: Plan how new work fits with existing systems
- **Testing Approach**: Identify relevant existing tests to extend
- **Compatibility Strategy**: Plan for offline-first and Termux support

#### 4. **Path Options Assessment** 🛤️
**When multiple implementation approaches exist, ALWAYS provide:**
- **Option A**: Recommended approach with reasoning
- **Option B**: Alternative approach with trade-offs
- **Option C**: Fallback approach for constrained environments
- **Compatibility Matrix**: How each option affects different platforms

## 📝 **MANDATORY WORK DOCUMENTATION PROTOCOL**

### **After Completing Major Work** 📊
**ALWAYS provide comprehensive work summary directly in chat:**

#### 1. **Problem Analysis** 🔍
- **Original Issue**: What problem was requested to be solved?
- **Root Cause**: What was the underlying cause?
- **Scope Assessment**: How extensive was the required work?

#### 2. **Solution Implementation** ⚙️
- **Approach Taken**: What strategy was used to solve the problem?
- **Files Modified**: List all files that were changed/created
- **Key Functions/Features Added**: Highlight main functionality implemented
- **Integration Points**: How the new code connects to existing systems

#### 3. **Before vs After Analysis** 📈
- **Before State**: Describe the system/functionality before changes
- **After State**: Describe the improved system/functionality after changes
- **Benefits Achieved**: List concrete improvements and benefits
- **Performance Impact**: Any performance improvements or considerations

#### 4. **Quality Assurance** ✅
- **Testing Performed**: What tests were run to validate the work
- **Cross-Platform Compatibility**: Verification across different environments
- **Offline Compatibility**: Confirmed functionality without internet
- **Termux Compatibility**: Verified operation in Android Termux environment
- **Edge Cases Handled**: Any special scenarios addressed
- **Future Maintenance**: Notes for future developers

#### 5. **Compatibility Assessment** 🌐
- **Offline Viability**: How the solution works without internet connectivity
- **Termux Performance**: Special considerations for Android/Termux environment
- **Resource Usage**: Memory, CPU, and battery impact on mobile devices
- **Fallback Options**: Alternative approaches for constrained environments
- **Path Recommendations**: Suggested implementation paths for different scenarios

#### 5. **Optional Detailed Documentation** 📚
**Note**: Detailed markdown documentation will only be created if specifically requested by the user.

### **Documentation Format Template** 📋
```
## 🎯 Work Summary: [Feature/Issue Name]

### Problem Solved:
- [Brief description of the issue]

### Implementation:
- [Key changes made]

### Benefits:
- [Concrete improvements achieved]

### Compatibility Status:
- ✅ Offline-friendly: [Yes/No with details]
- ✅ Termux-compatible: [Yes/No with details]
- ✅ Cross-platform: [Verified platforms]

### Files Modified:
- [List of changed files]

### Testing:
- [Validation performed]

### Alternative Paths Considered:
- [If applicable, list other approaches evaluated]
```
- **Memory usage**: Check streaming assembly configuration
- **Network optimization**: Tune timeout and retry settings

## 🎯 **WORKFLOW SUMMARY**

This project emphasizes real-time performance, cross-platform compatibility, offline-first design, and user experience with a focus on secure LAN-based file transfers that work universally across all environments.

### **Development Cycle** 🔄
1. **📊 SCAN**: Comprehensive project analysis including compatibility assessment
2. **🎯 PLAN**: Evaluate multiple implementation paths and compatibility requirements
3. **🔧 DEVELOP**: Follow modular, external-file-only, offline-first approach  
4. **✅ TEST**: Validate across platforms including desktop, Termux, online/offline scenarios
5. **📝 DOCUMENT**: Provide detailed work summary with compatibility status in chat
6. **🔍 REVIEW**: Assess impact, integration, and universal viability

### **Quality Standards** 🌟
- **Always scan before implementing** to understand existing functionality and compatibility requirements
- **Always assess offline/Termux viability** before choosing implementation approach
- **Always extend existing files** rather than creating new ones
- **Always use external CSS/JS files** instead of inline code
- **Always provide implementation path options** when multiple approaches exist
- **Always test across environments** (desktop, mobile, online, offline, Termux)
- **Always provide comprehensive work documentation** including compatibility assessment
- **Always ensure universal functionality** that works in all supported environments
