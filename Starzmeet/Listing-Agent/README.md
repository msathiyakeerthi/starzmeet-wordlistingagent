# WordPress Listing Agent

A powerful web scraper and WordPress integration tool for discovering and syncing autism services and neurodivergent support providers to WordPress ListingPro.

## Features

- 🔍 **AI-Powered Scraping**: Uses GPT-4 to extract detailed business information from websites
- 🗺️ **Google Maps Integration**: Searches 20+ targeted queries to find service providers
- 🔄 **WordPress Sync**: Bulk upload listings to WordPress ListingPro with duplicate detection
- 📊 **Real-time Progress**: WebSocket-powered live updates during scraping
- 🎯 **Smart Deduplication**: Avoids re-scraping existing places
- 📱 **Social Media Extraction**: Automatically finds Facebook, Instagram, Twitter, LinkedIn, YouTube links
- 🎨 **Modern UI**: Beautiful, responsive web interface

## Quick Start

### Prerequisites

- Python 3.8+
- Google Maps API Key
- OpenAI API Key
- WordPress site with ListingPro plugin

### Installation

1. Clone the repository:
```bash
git clone https://github.com/msathiyakeerthi/starzmeet-wordlistingagent.git
cd starzmeet-wordlistingagent
```

2. Install dependencies:
```bash
pip install flask flask-socketio flask-cors requests beautifulsoup4 openai python-dotenv pandas tenacity
```

3. Create `.env` file:
```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
OPENAI_API_KEY=your_openai_api_key
```

4. Run the server:
```bash
python app-latest-4.py
```

5. Open in browser:
- Home: http://localhost:5000/
- Manage: http://localhost:5000/manage
- View Data: http://localhost:5000/view_data

## WordPress Integration

### Setup

1. Go to **Manage → WordPress Sync** tab
2. Enter your WordPress URL (e.g., `https://starzmeet.com`)
3. Enter your API Key
4. Click **Save Configuration**

### Sync Modes

- **Skip Existing**: Only creates new listings (safest)
- **Update Existing**: Updates existing listings with fresh data (recommended)
- **Force Create**: Always creates new (may duplicate)

### Bulk Upload

- **Sync All**: Uploads all unsynced places
- **Sync by Location**: Uploads places from a specific location
- **Advanced Sync**: Select specific places to upload

## API Endpoints Used

- `GET /wp-json/listingpro/v1/listings` - List all listings
- `POST /wp-json/listingpro/v1/listing` - Create single listing
- `PUT /wp-json/listingpro/v1/listing/{id}` - Update listing
- `POST /wp-json/listingpro/v1/listings/bulk` - Bulk create listings

## Documentation

- [Complete System Guide](README_COMPLETE_SYSTEM.md)
- [WordPress Sync Guide](WORDPRESS_SYNC_GUIDE.md)
- [Quick Start Guide](QUICK_START.md)
- [Sync Modes Guide](SYNC_MODES_GUIDE.md)

## Project Structure

```
├── app-latest-4.py          # Main Flask application
├── templates/                # HTML templates
│   ├── index-late-2.html    # Home/Scraper page
│   ├── manage.html          # Management page
│   └── view_data.html       # Data viewer
├── *.md                     # Documentation files
└── .gitignore              # Git ignore rules
```

## License

This project is private and proprietary.

## Support

For issues or questions, please contact the repository owner.

