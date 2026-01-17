# Instagram Saved Posts Scraper

Extract your Instagram saved posts including images and captions.

## Features

- Download all your saved posts from Instagram
- Extract images (including carousel/multi-image posts)
- Extract video content and thumbnails
- Save post captions/text (not comments)
- Export to JSON with full metadata
- Export captions to plain text
- Session persistence (login once, reuse session)
- Supports two-factor authentication (2FA)
- Progress tracking and rate limiting

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Install dependencies

```bash
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install -e .
```

## Usage

### Quick Start

1. **Interactive login (recommended for first use):**

```bash
python run.py login -u your_username
```

This will prompt for your password and 2FA code if enabled, then save the session for future use.

2. **Scrape your saved posts:**

```bash
python run.py scrape -u your_username
```

### Command Line Options

#### Login Command

```bash
python run.py login --help
```

Options:
- `-u, --username` - Your Instagram username
- `-s, --session-file` - Custom path for session file

#### Scrape Command

```bash
python run.py scrape --help
```

Options:
- `-u, --username` - Your Instagram username (required)
- `-p, --password` - Your Instagram password (optional if using session)
- `-o, --output` - Output directory (default: `output`)
- `-n, --max-posts` - Maximum number of posts to scrape (default: all)
- `--no-media` - Skip downloading images and videos
- `--delay` - Delay between posts in seconds (default: 2.0)
- `-i, --interactive` - Use interactive login (required for 2FA)
- `-s, --session-file` - Path to session file

#### View Command

```bash
python run.py view output/saved_posts.json
```

Options:
- `-f, --format` - Output format: `table`, `json`, or `csv`
- `-n, --limit` - Number of posts to display

### Examples

**Scrape first 50 saved posts:**
```bash
python run.py scrape -u myusername -n 50
```

**Scrape without downloading media (metadata only):**
```bash
python run.py scrape -u myusername --no-media
```

**Use environment variables:**
```bash
export INSTAGRAM_USERNAME=myusername
python run.py scrape
```

**View scraped posts as CSV:**
```bash
python run.py view output/saved_posts.json -f csv > posts.csv
```

## Output Structure

After scraping, your output directory will contain:

```
output/
├── saved_posts.json          # Full metadata for all posts
├── captions.txt              # Plain text export of captions
└── <username>/
    └── <shortcode>/
        ├── image_1.jpg       # First image
        ├── image_2.jpg       # Additional images (carousel posts)
        ├── video.mp4         # Video file (if applicable)
        └── thumbnail.jpg     # Video thumbnail
```

### JSON Structure

The `saved_posts.json` file contains:

```json
{
  "scraped_at": "2024-01-15T10:30:00",
  "username": "your_username",
  "total_posts": 150,
  "posts": [
    {
      "shortcode": "ABC123xyz",
      "post_url": "https://www.instagram.com/p/ABC123xyz/",
      "owner_username": "some_account",
      "owner_full_name": "Some Account Name",
      "caption": "This is the post caption text...",
      "timestamp": "2024-01-10T15:30:00",
      "likes": 1234,
      "is_video": false,
      "image_urls": ["https://..."],
      "video_url": null,
      "local_image_paths": ["output/some_account/ABC123xyz/image_1.jpg"],
      "local_video_path": null
    }
  ]
}
```

## Configuration

You can use a `.env` file for configuration:

```bash
cp .env.example .env
```

Edit `.env`:
```
INSTAGRAM_USERNAME=your_username
```

## Two-Factor Authentication

If you have 2FA enabled on your Instagram account:

1. Use the interactive login:
   ```bash
   python run.py login -u your_username
   ```

2. Enter your password when prompted

3. Enter the 2FA code from your authenticator app

4. The session will be saved for future use

## Rate Limiting

Instagram has rate limits to prevent abuse. The scraper includes:

- Default 2-second delay between posts
- Automatic retry on temporary failures
- Session persistence to minimize logins

You can adjust the delay with `--delay`:
```bash
python run.py scrape -u myusername --delay 5
```

## Troubleshooting

### "Login required" error
Your session may have expired. Re-run the login command:
```bash
python run.py login -u your_username
```

### "Two-factor authentication required"
Use the interactive login flag:
```bash
python run.py scrape -u your_username -i
```

### Rate limited
Increase the delay between posts:
```bash
python run.py scrape -u your_username --delay 10
```

### Connection errors
The scraper will automatically retry on connection failures. If problems persist, try again later.

## Legal Notice

This tool is intended for personal use to backup your own Instagram saved posts. Please:

- Only use this tool with your own Instagram account
- Respect Instagram's Terms of Service
- Do not use for mass scraping or commercial purposes
- Downloaded content remains subject to original copyright

## License

MIT License
