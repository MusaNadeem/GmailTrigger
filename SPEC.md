# InboxIQ — Gmail Tagger Specification

## Project Overview
- **Project Name**: InboxIQ
- **Type**: Python CLI tool
- **Core Functionality**: Connect to Gmail via OAuth2, analyze recent emails using LLM, assign tags from YAML config, export to CSV
- **Target Users**: Anyone wanting automated email categorization

## Functionality Specification

### Core Features

1. **Gmail OAuth2 Connection**
   - Use Google OAuth2 with credentials.json (client secrets)
   - Store token in token.json for reuse
   - Fetch last 50 emails (configurable)
   - Extract: sender, subject, date, body snippet

2. **LLM Integration**
   - Support OpenAI API (primary)
   - Support Gemini API (secondary)
   - Send structured prompt with email content + available tags
   - Parse JSON response for tag assignment

3. **Tag Management**
   - Tags defined in `tags.yaml`
   - Hot-reload tags on each run (no restart needed)
   - Default tags: Invoice, Meeting, Spam, Follow-up, Newsletter, Personal, Urgent

4. **CSV Output**
   - File: `results.csv`
   - Columns: sender, subject, date, tag
   - Append mode to preserve history

5. **Logging**
   - Console output with timestamps
   - Show progress: "Processing email 1/50...", "Tagged: [subject] → Invoice"
   - Summary: "Completed: 50 emails tagged"

### Configuration Files

- `tags.yaml` — Tag definitions
- `config.yaml` — API keys, email count, etc.
- `credentials.json` — Gmail OAuth (user provides)
- `token.json` — Generated on first run

### User Flow
1. User sets up Gmail OAuth credentials
2. User adds API key to config.yaml
3. User edits tags.yaml with desired tags
4. Run: `python inboxiq.py`
5. Results appear in results.csv

## Acceptance Criteria
- [ ] Connects to Gmail and fetches emails
- [ ] Loads tags from YAML without restart
- [ ] Calls LLM API and receives tag response
- [ ] Writes results to CSV with correct columns
- [ ] Logs progress to console
- [ ] Handles API errors gracefully