# MCP Tools

**Total Tools:** 16

| Tool Name | Description | Language | File |
|-----------|-------------|----------|------|
| ApplicationInfo | Get comprehensive application information including PHP version, Laravel version... | PHP | src/Mcp/Tools/ApplicationInfo.php |
| BrowserLogs | Read the last N log entries from the BROWSER log. Very helpful for debugging the... | PHP | src/Mcp/Tools/BrowserLogs.php |
| DatabaseConnections | List the configured database connection names for this application. | PHP | src/Mcp/Tools/DatabaseConnections.php |
| DatabaseQuery | Execute a read-only SQL query against the configured database. | PHP | src/Mcp/Tools/DatabaseQuery.php |
| DatabaseSchema | Read the database schema for this application, including table names, columns, d... | PHP | src/Mcp/Tools/DatabaseSchema.php |
| GetAbsoluteUrl | Get the absolute URL for a given relative path or named route. If no arguments a... | PHP | src/Mcp/Tools/GetAbsoluteUrl.php |
| GetConfig | Get the value of a specific config variable using dot notation (e.g.,  | PHP | src/Mcp/Tools/GetConfig.php |
| LastError | Get details of the last error/exception created in this application on the backe... | PHP | src/Mcp/Tools/LastError.php |
| ListArtisanCommands | List all available Artisan commands registered in this application. | PHP | src/Mcp/Tools/ListArtisanCommands.php |
| ListAvailableConfigKeys | List all available Laravel configuration keys (from config/*.php) in dot notatio... | PHP | src/Mcp/Tools/ListAvailableConfigKeys.php |
| ListAvailableEnvVars | 🔧 List all available environment variable names from a given .env file (default ... | PHP | src/Mcp/Tools/ListAvailableEnvVars.php |
| ListRoutes | List all available routes defined in the application, including Folio routes if ... | PHP | src/Mcp/Tools/ListRoutes.php |
| ReadLogEntries | Read the last N log entries from the application log, correctly handling multi-l... | PHP | src/Mcp/Tools/ReadLogEntries.php |
| ReportFeedback | Report feedback from the user on what would make Boost, or their experience with... | PHP | src/Mcp/Tools/ReportFeedback.php |
| SearchDocs | Search for up-to-date version-specific documentation related to this project and... | PHP | src/Mcp/Tools/SearchDocs.php |
| Tinker | Execute PHP code in the Laravel application context, like artisan tinker. Use th... | PHP | src/Mcp/Tools/Tinker.php |