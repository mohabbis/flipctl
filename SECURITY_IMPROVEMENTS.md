# FlipCTL Security Improvements

This document outlines the security enhancements made to the FlipCTL prototype in response to a security audit.

## Vulnerabilities Addressed

### 1. Command Injection Vulnerabilities (CWE-78)
**Location:** `plugins/ping/main.py`, `plugins/nmap/main.py`
**Issue:** User-supplied `target` parameter was directly concatenated into subprocess commands without validation, allowing shell injection attacks.
**Fix:**
- Implemented comprehensive input validation using Python's `ipaddress` module for IP validation
- Added RFC-compliant hostname validation (length limits, character restrictions, hyphen placement rules)
- All user input is now validated before being passed to subprocess calls

**Example of fixed validation:**
```python
def is_valid_target(target: str) -> bool:
    # Validate IP address (IPv4 or IPv6)
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        pass

    # Validate hostname per RFC 1123/RFC 3696
    if len(target) > 253:
        return False
    if target.endswith('.'):
        target = target[:-1]
    # ... additional validation logic
```

### 2. Dangerous Stub Behavior (CWE-200)
**Location:** `plugins/nmap/main.py`
**Issue:** When nmap wasn't installed, the plugin returned fake data showing ports 22, 80, 443 as "open" - a serious security hazard that could lead to false positives and dangerous assumptions.
**Fix:**
- Removed all stub/fake data returns
- Now returns proper error: `{"success": false, "error": "nmap not installed"}`
- Implemented fail-fast approach to prevent dangerous misinformation

### 3. Missing Authentication (CWE-306)
**Location:** `server.py`
**Issue:** Server was exposed on 0.0.0.0 with zero authentication or rate limiting.
**Fix:**
- Added optional API key authentication (Bearer token)
- Implemented environment variable configuration (`FLIPCTL_API_KEY`)
- Added authentication middleware that validates tokens on protected endpoints
- Authentication can be toggled via configuration

### 4. Unrestricted Resource Consumption (CWE-770)
**Location:** `server.py`
**Issue:** No protection against excessive requests that could lead to DoS.
**Fix:**
- Added rate limiting (configurable requests per time window)
- Implemented sliding window algorithm using deque for efficiency
- Rate limiting can be tuned via configuration or disabled for trusted environments
- Added rate limit headers and logging for monitoring

### 5. Reliance on Untrusted Inputs in Security Decisions (CWE-807)
**Location:** Multiple locations in plugin system
**Issue:** Various components made security decisions based on unvalidated input.
**Fix:**
- Plugin manager now uses `shell=False` explicitly in all subprocess calls
- Working directory is strictly controlled to plugin directory
- Input is passed via stdin as JSON (no shell interpolation)
- Timeout limits prevent DoS via hanging processes

### 6. Fragile Output Parsing
**Location:** `plugins/nmap/main.py`
**Issue:** Fragile regex parsing of human-readable nmap output that breaks across locales and versions.
**Fix:**
- Changed from parsing greppable output (`-oG`) to XML output (`-oX`)
- Now uses `xml.etree.ElementTree` for robust, structured parsing
- Much more resilient to output format changes and localization differences
- Proper error handling for XML parsing failures

## Security Features Summary

### Input Validation
- ✅ IP address validation (IPv4/IPv6)
- ✅ RFC-compliant hostname validation
- ✅ Command injection prevention
- ✅ Length and character set restrictions

### Authentication & Authorization
- ✅ Optional API key authentication (Bearer token)
- ✅ Environment variable configuration
- ✅ Auth middleware for endpoint protection
- ✅ Configurable enable/disable

### Rate Limiting & DoS Protection
- ✅ Configurable request quotas
- ✅ Sliding window algorithm
- ✅ Per-client IP tracking
- ✅ Exhaustive logging of rate limit events

### Secure Execution Environment
- ✅ Explicit `shell=False` in subprocess calls
- ✅ Working directory restriction to plugin directory
- ✅ Input via JSON stdin (no shell interpolation)
- ✅ Process timeout limits
- ✅ Framework for plugin sandboxing (future enhancement)

### Reliable Data Handling
- ✅ XML-based output parsing for nmap
- ✅ Structured error handling
- ✅ Fail-fast approach for missing dependencies
- ✅ No dangerous stub or fallback data

### Logging & Monitoring
- ✅ Structured logging with configurable levels
- ✅ Security-relevant events (auth failures, rate limits)
- ✅ Audit trail for plugin executions
- ✅ Health check endpoint for monitoring

## Configuration

Security features are configurable via:
1. **Environment Variables:**
   - `FLIPCTL_API_KEY` - API key for authentication
   - `FLIPCTL_AUTH_ENABLED` - "true"/"false" to enable/disable auth
   - `FLIPCTL_RATE_LIMIT_REQUESTS` - Requests per window (default: 10)
   - `FLIPCTL_RATE_LIMIT_WINDOW` - Window size in seconds (default: 60)
   - `FLIPCTLIPCTL_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

2. **Runtime Configuration** (via config system):
   - Settings persisted to `~/.flipctl/config.json`
   - Can be modified at runtime through administrative interfaces

## Usage Examples

### Setting up Authentication
```bash
export FLIPCTL_API_KEY="your-secure-random-key-here"
export FLIPCTL_AUTH_ENABLED="true"
```

### Adjusting Rate Limits
```bash
export FLIPCTL_RATE_LIMIT_REQUESTS="100"  # 100 requests
export FLIPCTL_RATE_LIMIT_WINDOW="60"     # per minute
```

### Running with Enhanced Logging
```bash
export FLIPCTL_LOG_LEVEL="DEBUG"
```

## Verification

The security improvements have been verified through:
1. **Syntax validation:** All modified Python files compile without errors
2. **Code review:** Manual inspection confirms correct implementation
3. **Test suite:** Comprehensive unit tests for:
   - Input validation (valid/invalid inputs)
   - Authentication flows
   - Rate limiting behavior
   - Plugin execution security
   - Error handling scenarios

## Future Enhancements

Planned security improvements:
1. **Plugin Sandboxing:** Full implementation of process isolation for plugin execution
2. **Certificate Pinning:** For secure service-to-service communication
3. **Audit Logging:** Cryptographically signed audit trails
4. **Secrets Management:** Integration with system keyring or vault services
5. **CORS Hardening:** More restrictive CORS policies
6. **Security Headers:** Addition of HSTS, CSP, and other protective headers

## Conclusion

These security improvements transform the FlipCTL prototype from a vulnerable demonstration into a security-conscious foundation suitable for further development and testing in controlled environments. The defense-in-depth approach addresses multiple attack vectors while maintaining usability and extensibility.

**Note:** While these improvements significantly enhance security, any production deployment should include:
- Penetration testing
- Regular security audits
- Continuous monitoring
- Keeping dependencies updated
- Following principle of least privilege for service accounts