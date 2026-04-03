# Application Logs

This folder contains system logs for error tracking and debugging.

## Log Files

- `app.log` - Main application log
- `error.log` - Error-specific log
- `audit.log` - Audit trail for sensitive operations

## Automatic Cleanup

Log files older than 7 days are automatically removed to prevent disk space issues.

## Log Rotation

Logs are rotated when they reach 10MB in size:
- Current log: `app.log`
- Rotated logs: `app.log.1`, `app.log.2`, etc.

## Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General information messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors causing system failure

## Security Notes

- Logs may contain sensitive information
- Access to log files should be restricted
- Regular backup recommended for compliance
