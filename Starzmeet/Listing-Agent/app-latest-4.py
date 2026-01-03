import os
import time
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import openai
import logging
import re
from datetime import datetime
import tempfile
import uuid
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import glob
import sqlite3
import socket

from contextlib import contextmanager
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY is not set in environment variables")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in environment variables")

openai.api_key = OPENAI_API_KEY

# SQLite database setup
DB_PATH = "autism_services.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # Places table
        c.execute('''
            CREATE TABLE IF NOT EXISTS places (
                place_id TEXT PRIMARY KEY,
                location TEXT,
                scraped_at TEXT,
                data JSON,
                wp_synced INTEGER DEFAULT 0,
                wp_post_id INTEGER,
                wp_sync_date TEXT
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_location ON places (location)')
        
        # Keywords table
        c.execute('''
            CREATE TABLE IF NOT EXISTS search_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT,
                last_used TEXT
            )
        ''')
        
        # Initialize default keywords if table is empty
        c.execute("SELECT COUNT(*) FROM search_keywords")
        if c.fetchone()[0] == 0:
            default_keywords = [
                ('autism therapy centers', 'Autism Core'),
                ('autism treatment clinics', 'Autism Core'),
                ('autism support services', 'Autism Core'),
                ('ABA therapy centers', 'Autism Core'),
                ('autism behavioral therapy', 'Autism Core'),
                ('autism diagnostic centers', 'Autism Core'),
                ('developmental disabilities services', 'Autism Core'),
                ('special needs therapy', 'Autism Core'),
                ('ADHD therapy centers', 'ADHD'),
                ('ADHD coaching clinics', 'ADHD'),
                ('behavioral therapy ADHD', 'ADHD'),
                ('parent training autism ADHD', 'ADHD'),
                ('speech therapy autism ADHD', 'Therapy'),
                ('occupational therapy sensory integration', 'Therapy'),
                ('sensory integration therapy', 'Therapy'),
                ('sensory gyms autism ADHD', 'Therapy'),
                ('dyslexia learning centers', 'Learning'),
                ('learning disability centers', 'Learning'),
                ('social skills groups autism ADHD', 'Community'),
                ('special needs camps autism ADHD', 'Community'),
                ('adaptive sports autism ADHD', 'Community'),
                ('autism ADHD inclusive recreation centers', 'Community'),
                ('autism ADHD support groups', 'Community')
            ]
            created_at = datetime.now().isoformat()
            for keyword, category in default_keywords:
                c.execute("INSERT INTO search_keywords (keyword, category, active, created_at) VALUES (?, ?, 1, ?)",
                         (keyword, category, created_at))
        
        conn.commit()

init_db()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

# Clean up old temporary files
def cleanup_temp_files():
    temp_dir = tempfile.gettempdir()
    pattern = os.path.join(temp_dir, "autism_services_export_*.csv")
    for temp_file in glob.glob(pattern):
        try:
            os.remove(temp_file)
            logger.info(f"Deleted old temp file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to delete old temp file: {temp_file}: {e}")

cleanup_temp_files()

def is_domain_resolvable(url):
    try:
        domain = url.split("//")[-1].split("/")[0]
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False

# ==================== Scraper Class ====================
class GoogleMapsAutismDataScraperV2:
    def __init__(self, api_key, socketio=None):
        self.api_key = api_key
        self.socketio = socketio
        self.base_url = "https://places.googleapis.com/v1/places:searchText"
        self.place_details_url = "https://places.googleapis.com/v1/places"
        self.new_results = []
        self.all_results = []

    def extract_social_links(self, soup):
        social_links = {
            'Twitter': '',
            'Facebook': '',
            'LinkedIn': '',
            'Google_plus': '',
            'YouTube': '',
            'Instagram': '',
            'Youtube Video URL': ''
        }

        # First: extract from anchor tags
        for a in soup.find_all('a', href=True):
            href = a['href'].strip().lower()

            if not social_links['Twitter'] and 'twitter.com' in href:
                social_links['Twitter'] = a['href']
            elif not social_links['Facebook'] and 'facebook.com' in href:
                social_links['Facebook'] = a['href']
            elif not social_links['LinkedIn'] and 'linkedin.com' in href:
                social_links['LinkedIn'] = a['href']
            elif not social_links['Google_plus'] and 'plus.google.com' in href:
                social_links['Google_plus'] = a['href']
            elif not social_links['YouTube'] and ('youtube.com/channel' in href or 'youtube.com/user' in href):
                social_links['YouTube'] = a['href']
            elif not social_links['Youtube Video URL'] and ('youtube.com/watch' in href or 'youtu.be' in href):
                social_links['Youtube Video URL'] = a['href']
            elif not social_links['Instagram'] and 'instagram.com' in href:
                social_links['Instagram'] = a['href']
        return social_links



    def extract_logo_and_banner(self, soup, base_url):
        logo_url = banner_url = ""
        for tag in soup.select('header img, nav img, .logo img'):
            src = tag.get("src", "")
            if src and "logo" in src.lower():
                logo_url = urljoin(base_url, src)
                break
        for section in soup.select('[class*="hero"], [class*="banner"], [class*="slider"]'):
            style = section.get("style", "")
            if "background-image" in style:
                match = re.search(r'url\((.*?)\)', style)
                if match:
                    banner_url = urljoin(base_url, match.group(1).strip('"\'')) 
                    break
        if not banner_url:
            for img in soup.select('[class*="hero"] img, [class*="banner"] img, [class*="slider"] img'):
                src = img.get("src", "")
                if src and src != logo_url:
                    banner_url = urljoin(base_url, src)
                    break
        if not banner_url and soup.find_all("img"):
            candidates = [(int(img.get("width") or 0) * int(img.get("height") or 0), urljoin(base_url, img.get("src", "")))
                          for img in soup.find_all("img") if img.get("src") and img.get("src") != logo_url]
            if candidates:
                banner_url = max(candidates, key=lambda x: x[0])[1]
        return logo_url, banner_url

    def extract_photo_urls(self, photos):
        if not photos:
            return []
        return [
            f"https://places.googleapis.com/v1/{photo.get('name')}/media?maxHeightPx=500&key={self.api_key}"
            for photo in photos if photo.get('name')
        ]

    def get_existing_place_ids(self, location):
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT place_id FROM places WHERE location LIKE ?", (f"%{location}%",))
            return {row[0] for row in c.fetchall()}

    def get_existing_places(self, location):
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places WHERE location LIKE ?", (f"%{location}%",))
            return [json.loads(row[0]) for row in c.fetchall()]

    def save_place(self, place, location):
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO places (place_id, location, scraped_at, data) VALUES (?, ?, ?, ?)",
                (place['Place ID'], location, datetime.now().isoformat(), json.dumps(place))
            )
            conn.commit()

    def search_autism_services(self, location="California", max_results=100):
        existing_place_ids = self.get_existing_place_ids(location)
        search_queries = [
            # Autism core
            f"autism therapy centers in {location}",
            f"autism treatment clinics in {location}",
            f"autism support services in {location}",
            f"ABA therapy centers in {location}",
            f"autism behavioral therapy in {location}",
            f"autism diagnostic centers in {location}",
            f"developmental disabilities services in {location}",
            f"special needs therapy in {location}",

            # ADHD
            f"ADHD therapy centers in {location}",
            f"ADHD coaching clinics in {location}",
            f"behavioral therapy ADHD in {location}",
            f"parent training autism ADHD in {location}",

            # Speech / OT / Sensory
            f"speech therapy autism ADHD in {location}",
            f"occupational therapy sensory integration in {location}",
            f"sensory integration therapy in {location}",
            f"sensory gyms autism ADHD in {location}",

            # Learning & Dyslexia
            f"dyslexia learning centers in {location}",
            f"learning disability centers in {location}",

            # Community & Recreation
            f"social skills groups autism ADHD in {location}",
            f"special needs camps autism ADHD in {location}",
            f"adaptive sports autism ADHD in {location}",
            f"autism ADHD inclusive recreation centers in {location}",
            f"autism ADHD support groups in {location}"
        ]

        all_places = []
        for query in search_queries:
            try:
                logger.info(f"Searching query: {query}")
                places = self._search_text(query, max_results_per_query=20)
                new_places = [p for p in places if p.get('id') not in existing_place_ids]
                all_places.extend(new_places)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error searching for {query}: {str(e)}")
                if self.socketio:
                    self.socketio.emit('error', {'message': f"Search failed for {query}: {str(e)}"}, namespace='/')
        unique_places = {p['id']: p for p in all_places if 'id' in p}
        return list(unique_places.values())[:max_results]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.HTTPError))
    )
    def _search_text(self, query, max_results_per_query=20):
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.api_key,
            'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel,places.businessStatus,places.types,places.websiteUri,places.nationalPhoneNumber,places.internationalPhoneNumber,places.regularOpeningHours,places.editorialSummary,places.photos,places.reviews,places.googleMapsUri'
        }
        payload = {
            "textQuery": query,
            "maxResultCount": max_results_per_query
        }
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get('places', [])

    def get_place_details(self, place_id):
        try:
            url = f"{self.place_details_url}/{place_id}"
            headers = {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': 'id,displayName,formattedAddress,location,rating,userRatingCount,priceLevel,businessStatus,types,websiteUri,nationalPhoneNumber,internationalPhoneNumber,regularOpeningHours,editorialSummary,photos,reviews,googleMapsUri'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching details for place_id {place_id}: {e}")
            if self.socketio:
                self.socketio.emit('error', {'message': f"Failed to fetch details for place_id {place_id}: {str(e)}"}, namespace='/')
            return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.SSLError))
    )
    def enrich_with_openai(self, website_url):
        social_links = {
            'Twitter': '',
            'Facebook': '',
            'LinkedIn': '',
            'Google_plus': '',
            'YouTube': '',
            'Instagram': '',
            'Youtube Video URL': ''
        }
        logo_url = ""
        banner_url = ""

        try:
            if not website_url or not is_domain_resolvable(website_url):
                logger.warning(f"Skipping enrichment: Cannot resolve {website_url}")
                if self.socketio:
                    self.socketio.emit('error', {
                        'message': f"DNS resolution failed for {website_url}. Skipping enrichment."
                    }, namespace='/')
                return {**social_links, "Logo Image": logo_url, "Banner Image": banner_url}


            logger.info(f"Enriching website: {website_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }

            try:
                response = requests.get(website_url, headers=headers, timeout=30, verify=True)
                response.raise_for_status()
            except requests.exceptions.SSLError:
                if website_url.startswith("https://"):
                    fallback_url = website_url.replace("https://", "http://")
                    logger.warning(f"SSL error – retrying with HTTP: {fallback_url}")
                    response = requests.get(fallback_url, headers=headers, timeout=30, verify=False)
                    response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(separator='\n', strip=True)

            # Extract links/images
            social_links = self.extract_social_links(soup)
            logo_url, banner_url = self.extract_logo_and_banner(soup, website_url)

            # Truncate page_text to fit within OpenAI token limits
            truncated_text = page_text[:4000]
            prompt = f"""
            You are a smart business listing assistant.
            From the web page content below, extract and return unique metadata for the specific organization.
            Ensure the description is tailored to the organization and not generic.
            Fields to extract in JSON format:
            1. Description:
               - About: A unique summary of what this organization does from aboutus and home page(300-500 words).
               - Services: List of specific services and programs offered (as a list).
               - Contact Info: Include phone, email, and address if found.
            2. Tagline: A short, unique slogan or mission phrase.
            3. Email: Main contact email address.
            4. Category: Type of business (e.g., ABA Therapy, Autism Center).
            5. Features: Unique highlights (e.g., in-home service, multilingual staff) as Comma-separated list.
            6. Tags: Comma-separated list of keywords (e.g., autism, ABA, therapy).
            Be concise, accurate, and use only information from the page. Avoid generic responses.
            Return clean JSON only.
            Website Content:
            {truncated_text}
            """
            client = openai.OpenAI()
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You extract structured, unique business listing metadata from websites."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.6
            )
            content = completion.choices[0].message.content.strip()
            print("\n========= OpenAI RAW RESPONSE =========")
            print(content)
            print("=======================================\n")
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            try:
                data = json.loads(content.strip())
                if isinstance(data.get("Description"), dict):
                    desc = data["Description"]
                    html_parts = []
                    if "About" in desc:
                        html_parts.append(f'<h3 style="color: #333; font-size: 18px; margin-bottom: 10px;">About the business</h3>')
                        html_parts.append(f'<p style="color: #555; font-size: 14px; line-height: 1.5;">{desc["About"]}</p>')
                    if "Services" in desc and isinstance(desc["Services"], list):
                        service_list = '<ul style="color: #555; font-size: 14px; line-height: 1.5; padding-left: 20px;">' + ''.join(f'<li>{s}</li>' for s in desc["Services"]) + '</ul>'
                        html_parts.append(f'<h3 style="color: #333; font-size: 18px; margin: 15px 0 10px;">Services</h3>')
                        html_parts.append(service_list)
                    contact_info = desc.get("Contact Info", {})

                    def flatten_and_strip(value):
                        if isinstance(value, list):
                            return ", ".join(v.strip() for v in value if isinstance(v, str))
                        elif isinstance(value, str):
                            return value.strip()
                        return ""

                    phone = flatten_and_strip(contact_info.get("Phone"))
                    email = flatten_and_strip(contact_info.get("Email"))
                    address = flatten_and_strip(contact_info.get("Address"))



                    if phone or email or address:
                        contact_html = '<h3 style="color: #333; font-size: 18px; margin: 15px 0 10px;">Contact Info</h3>'
                        contact_html += '<p style="color: #555; font-size: 14px; line-height: 1.5;">'
                        if phone:
                            contact_html += f'<strong>Phone:</strong> {phone}<br>'
                        if email:
                            contact_html += f'<strong>Email:</strong> {email}<br>'
                        if address:
                            contact_html += f'<strong>Address:</strong> {address}'
                        contact_html += '</p>'
                        html_parts.append(contact_html)
                    else:
                        print(f"⚠️ OpenAI returned no Contact Info block: {contact_info}")

                    data["Description"] = '<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 10px; background-color: #dbf0f5;">' + ''.join(html_parts) + '</div>'
                data.update(social_links)
                data["Logo Image"] = logo_url
                data["Banner Image"] = banner_url
                return data
            except json.JSONDecodeError as e:
                logger.error(f"OpenAI returned invalid JSON for {website_url}: {content}, error: {e}")
                if self.socketio:
                    self.socketio.emit('error', {'message': f"Invalid JSON from OpenAI for {website_url}"}, namespace='/')
                return {**social_links, "Logo Image": logo_url, "Banner Image": banner_url}
        except Exception as e:
            logger.error(f"OpenAI enrichment failed for {website_url}: {str(e)}")
            if self.socketio:
                self.socketio.emit('error', {'message': f"Enrichment failed for {website_url}: {str(e)}"}, namespace='/')
            return {**social_links, "Logo Image": logo_url, "Banner Image": banner_url}

    def extract_price_info(self, price_level):
        price_map = {
            "PRICE_LEVEL_FREE": ("Free", "0", "0"),
            "PRICE_LEVEL_INEXPENSIVE": ("$", "1", "50"),
            "PRICE_LEVEL_MODERATE": ("$$", "51", "100"),
            "PRICE_LEVEL_EXPENSIVE": ("$$$", "101", "200"),
            "PRICE_LEVEL_VERY_EXPENSIVE": ("$$$$", "201", "500")
        }
        return price_map.get(price_level, ("", "", ""))

    def format_business_hours(self, opening_hours):
        if not opening_hours or 'weekdayDescriptions' not in opening_hours:
            return ""
        formatted_hours = []
        def clean_time(t):
            t = re.sub(r'([AP]M)', r' \1', t)
            t = t.replace("\u202f", "").strip()
            try:
                return datetime.strptime(t, "%I:%M %p").strftime("%H:%M")
            except:
                return t
        for line in opening_hours['weekdayDescriptions']:
            try:
                day, times = line.split(": ")
                if 'Closed' in times:
                    formatted_hours.append(f"{day},Closed,Closed")
                else:
                    open_time, close_time = map(clean_time, map(str.strip, times.split("–")))
                    formatted_hours.append(f"{day},{open_time},{close_time}")
            except Exception as e:
                logger.error(f"Error parsing business hours: {e}")
        return "|".join(formatted_hours)

    def process_places(self, places, location):
        total_places = len(places)
        logger.info(f"Processing {total_places} new places for {location}")
        self.new_results = []
        if total_places == 0:
            if self.socketio:
                self.socketio.emit('progress', {
                    'completed': 0,
                    'total': 0,
                    'message': f"No new places found for {location}"
                }, namespace='/')
        for idx, place in enumerate(places, 1):
            logger.info(f"Processing place {idx}/{total_places}: {place.get('displayName', {}).get('text', 'Unknown')}")
            details = self.get_place_details(place['id'])
            merged = {**place, **details}
            location_data = merged.get('location', {})
            name = merged.get('displayName', {}).get('text', '')
            website = merged.get('websiteUri', '')
            openai_data = self.enrich_with_openai(website)
            price_status, price_from, price_to = self.extract_price_info(merged.get('priceLevel'))

            # Use OpenAI description if available; otherwise, create a minimal unique description
            description = openai_data.get('Description')
            if not description:
                description = f'<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0; padding: 10px;"><p style="color: #555; font-size: 14px; line-height: 1.5;">{name} provides autism-related services in {location}. Please visit their website for more information.</p></div>'

            result = {
                'Place ID': place['id'],
                'Title': name,
                'Description': description,
                'Tagline': openai_data.get('Tagline', ''),
                'Google Address': merged.get('formattedAddress', ''),
                'Latitude': location_data.get('latitude', ''),
                'Longitude': location_data.get('longitude', ''),
                'Phone': merged.get('nationalPhoneNumber', '') or merged.get('internationalPhoneNumber', ''),
                'Email': openai_data.get('Email', ''),
                'Website': website,
                'Twitter': openai_data.get('Twitter', ''),
                'Facebook': openai_data.get('Facebook', ''),
                'Linkedin': openai_data.get('LinkedIn', ''),
                'Google_plus': '',
                'Youtube': openai_data.get('YouTube', ''),
                'Instagram': openai_data.get('Instagram', ''),
                'Youtube Video URL': openai_data.get('Youtube Video URL', ''),
                'Logo Image': openai_data.get('Logo Image', ''),
                'Banner Image': openai_data.get('Banner Image', ''),
                'Price Status ($-moderate)': price_status,
                'Price From': price_from,
                'Price To': price_to,
                'Claim Status': merged.get('businessStatus', ''),
                'Faq Question (sep. by pipe sign | )': '',
                'Faq Answer (sep. by pipe sign | )': '',
                'Gallery': ','.join(self.extract_photo_urls(merged.get('photos', []))),
                'Pricing Plan ID': '',
                'Business Hours (Day,OpenTime,CloseTime)': self.format_business_hours(merged.get('regularOpeningHours')),
                'Category': openai_data.get('Category', 'Autism Services'),
                'Features': openai_data.get('Features', ''),
                'Tags (Keywords)': openai_data.get('Tags (Keywords)') or openai_data.get('Tags') or openai_data.get('tags', ''),
                'Location': self.get_location_from_address_llm(merged.get('formattedAddress', '')),
                'Status': 'New'
            }
            self.new_results.append(result)
            self.all_results.append(result)
            self.save_place(result, location)
            if self.socketio:
                logger.info(f"Emitting progress event for place {idx}/{total_places}")
                self.socketio.emit('progress', {
                    'completed': idx,
                    'total': total_places,
                    'place': result
                }, namespace='/')
                self.socketio.sleep(0)
            time.sleep(0.5)
        # Load existing places after processing new ones
        existing_places = self.get_existing_places(location)
        for place in existing_places:
            if place['Place ID'] not in {p['Place ID'] for p in self.new_results}:
                place['Status'] = 'Old'
                self.all_results.append(place)
        logger.info(f"Completed processing {total_places} new places, total {len(self.all_results)} places including historical")

    def retry_place(self, place_id, website, address):
        try:
            logger.info(f"Retrying place_id: {place_id}, website: {website}, address: {address}")
            openai_data = self.enrich_with_openai(website)
            location_str = self.get_location_from_address_llm(address)
            details = self.get_place_details(place_id)
            merged = {**details}
            location = merged.get('location', {})
            name = merged.get('displayName', {}).get('text', '')
            price_status, price_from, price_to = self.extract_price_info(merged.get('priceLevel'))

            description = openai_data.get('Description')
            if not description:
                description = f'<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0; padding: 10px;"><p style="color: #555; font-size: 14px; line-height: 1.5;">{name} provides autism-related services in {location_str}. Please visit their website for more information.</p></div>'

            updated_result = {
                'Place ID': place_id,
                'Title': name,
                'Description': description,
                'Tagline': openai_data.get('Tagline', ''),
                'Google Address': merged.get('formattedAddress', ''),
                'Latitude': location.get('latitude', ''),
                'Longitude': location.get('longitude', ''),
                'Phone': merged.get('nationalPhoneNumber', '') or merged.get('internationalPhoneNumber', ''),
                'Email': openai_data.get('Email', ''),
                'Website': website,
                'Twitter': openai_data.get('Twitter', ''),
                'Facebook': openai_data.get('Facebook', ''),
                'Linkedin': openai_data.get('LinkedIn', ''),
                'Google_plus': '',
                'Youtube': openai_data.get('YouTube', ''),
                'Instagram': openai_data.get('Instagram', ''),
                'Youtube Video URL': openai_data.get('Youtube Video URL', ''),
                'Logo Image': openai_data.get('Logo Image', ''),
                'Banner Image': openai_data.get('Banner Image', ''),
                'Price Status ($-moderate)': price_status,
                'Price From': price_from,
                'Price To': price_to,
                'Claim Status': merged.get('businessStatus', ''),
                'Faq Question (sep. by pipe sign | )': '',
                'Faq Answer (sep. by pipe sign | )': '',
                'Gallery': ','.join(self.extract_photo_urls(merged.get('photos', []))),
                'Pricing Plan ID': '',
                'Business Hours (Day,OpenTime,CloseTime)': self.format_business_hours(merged.get('regularOpeningHours')),
                'Category': openai_data.get('Category', 'Autism Services'),
                'Features': openai_data.get('Features', ''),
                'Tags (Keywords)': openai_data.get('Tags (Keywords)') or openai_data.get('Tags') or openai_data.get('tags', ''),
                'Location': location_str,
                'Status': 'New'
            }

            # Update in-memory results
            for idx, result in enumerate(self.new_results):
                if result['Place ID'] == place_id:
                    self.new_results[idx] = updated_result
                    break
            for idx, result in enumerate(self.all_results):
                if result['Place ID'] == place_id:
                    self.all_results[idx] = updated_result
                    break
            # Update database
            self.save_place(updated_result, updated_result['Location'].split(' > ')[-1])

            if self.socketio:
                logger.info(f"Emitting retry_progress event for place_id {place_id}")
                self.socketio.emit('retry_progress', {
                    'place_id': place_id,
                    'place': updated_result
                }, namespace='/')
            return updated_result
        except Exception as e:
            logger.error(f"Retry failed for place_id {place_id}: {str(e)}")
            if self.socketio:
                self.socketio.emit('error', {'message': f"Retry failed for place_id {place_id}: {str(e)}"}, namespace='/')
            return None

    def run_scraper(self, max_results=100, location="California"):
        logger.info(f"Scraping {location} with {max_results} results")
        self.new_results = []
        self.all_results = []
        # Load existing places first
        existing_places = self.get_existing_places(location)
        for place in existing_places:
            place['Status'] = 'Old'
            self.all_results.append(place)
        # Emit existing places to UI
        if self.socketio:
            for place in self.all_results:
                self.socketio.emit('progress', {
                    'completed': 0,
                    'total': 0,
                    'place': place,
                    'message': f"Loaded existing place: {place['Title']}"
                }, namespace='/')
                self.socketio.sleep(0)
        # Scrape new places
        places = self.search_autism_services(location=location, max_results=max_results)
        self.process_places(places, location)

    def get_location_from_address_llm(self, address):
        try:
            if not address:
                return ""
            # Handle Singapore addresses
            if 'singapore' in address.lower():
                match = re.search(r'^(?:.*?, )?Singapore\s*(\d{6})?$', address, re.IGNORECASE)
                if match:
                    return "Singapore > Singapore > Singapore"
            # Handle UAE addresses
            if 'dubai' in address.lower():
                match = re.search(r'^(?:.*?, )?Dubai(?:, United Arab Emirates)?$', address, re.IGNORECASE)
                if match or 'dubai' in address.lower():
                    return "United Arab Emirates > Dubai > Dubai"
            # Try US-style addresses
            match = re.search(r'^(?:.*?, )?([A-Za-z\s]+),\s*([A-Z]{2})(?:\s*\d{5})?$', address)
            if match:
                city, state = match.groups()
                return f"United States > {state} > {city}"
            
            # Fallback to LLM for other addresses
            prompt = f"""
            You are a location classifier that extracts country, state/province, and city from addresses.
            Address: {address}
            Rules:
            - For city-states like Singapore, return {{"country": "Singapore", "state": "Singapore", "city": "Singapore"}}.
            - For UAE addresses containing 'Dubai', return {{"country": "United Arab Emirates", "state": "Dubai", "city": "Dubai"}}.
            - For US addresses, extract state (e.g., TX) and city.
            - If country is not specified, assume 'United States' unless address suggests otherwise (e.g., Dubai, Singapore).
            - Return a JSON object with 'country', 'state', and 'city' fields.
            - Ensure valid JSON format (e.g., {{"country": "value", "state": "value", "city": "value"}}).
            - Do not include ```json or any markdown.
            Examples:
            - "123 Main St, Frisco, TX 75034" → {{"country": "United States", "state": "Texas", "city": "Frisco"}}
            - "Al Barsha 1, Dubai" → {{"country": "United Arab Emirates", "state": "Dubai", "city": "Dubai"}}
            """

            client = openai.OpenAI()
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a location classifier that extracts country, state, and city from addresses."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            content = completion.choices[0].message.content.strip()
            try:
                location_data = json.loads(content)
                country = location_data.get('country', '')
                state = location_data.get('state', '')
                city = location_data.get('city', '')
                if country and state and city:
                    return f"{country} > {state} > {city}"
                else:
                    logger.warning(f"Incomplete location data from LLM: {location_data}")
                    return city or address.split(',')[-1].strip() or ""
            except json.JSONDecodeError as e:
                logger.error(f"OpenAI returned invalid JSON for location: {content}, error: {e}")
                if self.socketio:
                    self.socketio.emit('error', {'message': f"Invalid JSON from OpenAI for address {address}"}, namespace='/')
                return address.split(',')[-1].strip() or ""
        except Exception as e:
            logger.error(f"Error fetching location from address using LLM: {e}")
            if self.socketio:
                self.socketio.emit('error', {'message': f"Failed to extract location from address: {str(e)}"}, namespace='/')
            return address.split(',')[-1].strip() or ""

# ==================== Flask App ====================
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

scraper = GoogleMapsAutismDataScraperV2(API_KEY, socketio)

@app.route('/')
def home():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM places")
        total_places = c.fetchone()[0]
    return render_template("index-late-2.html", total_places=total_places)

@app.route('/view_data')
def view_data():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT data FROM places")
        places = [json.loads(row[0]) for row in c.fetchall()]
        c.execute("SELECT COUNT(*) FROM places")
        total_places = c.fetchone()[0]
    return render_template("view_data.html", places=places, total_places=total_places)

@app.route('/api/search')
def api_search():
    try:
        location = request.args.get("location", "California")
        max_results = int(request.args.get("max_results", 10))
        if max_results < 1 or max_results > 100:
            return jsonify({"error": "max_results must be between 1 and 100"}), 400
        logger.info(f"Starting background task for location={location}, max_results={max_results}")
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM places WHERE location LIKE ?", (f"%{location}%",))
            known_places = c.fetchone()[0]
        socketio.emit('info', {
            'message': f"{known_places} places already known for {location}. Fetching new places..."
        }, namespace='/')
        socketio.start_background_task(scraper.run_scraper, max_results=max_results, location=location)
        return jsonify({"status": "Scraping started", "known_places": known_places})
    except Exception as e:
        logger.error(f"Error in /api/search: {str(e)}")
        socketio.emit('error', {'message': f"Search failed: {str(e)}"}, namespace='/')
        return jsonify({"error": str(e)}), 500

@app.route('/api/retry_place', methods=['POST'])
def api_retry_place():
    try:
        data = request.get_json()
        place_id = data.get('place_id')
        website = data.get('website')
        address = data.get('address')
        if not place_id or not address:
            return jsonify({"error": "place_id and address are required"}), 400
        logger.info(f"Received retry request for place_id: {place_id}")
        updated_result = scraper.retry_place(place_id, website, address)
        if updated_result:
            return jsonify({"status": "Retry successful", "place": updated_result})
        else:
            return jsonify({"error": "Retry failed"}), 500
    except Exception as e:
        logger.error(f"Error in /api/retry_place: {str(e)}")
        socketio.emit('error', {'message': f"Retry failed: {str(e)}"}, namespace='/')
        return jsonify({"error": str(e)}), 500

@app.route('/api/download')
def api_download():
    try:
        location = request.args.get("location", None)
        status = request.args.get("status", None)
        expected_columns = [
            'Status', 'Title', 'Description', 'Tagline', 'Google Address', 'Latitude', 'Longitude',
            'Phone', 'Email', 'Website', 'Twitter', 'Facebook', 'Linkedin', 'Google_plus',
            'Youtube', 'Instagram', 'Youtube Video URL',
            'Logo Image', 'Banner Image',
            'Price Status ($-moderate)', 'Price From', 'Price To',
            'Claim Status', 'Faq Question (sep. by pipe sign | )', 'Faq Answer (sep. by pipe sign | )',
            'Gallery', 'Pricing Plan ID', 'Business Hours (Day,OpenTime,CloseTime)',
            'Category', 'Features', 'Tags (Keywords)', 'Location'
        ]
        with get_db() as conn:
            c = conn.cursor()
            query = "SELECT data FROM places"
            params = []
            conditions = []
            if location:
                conditions.append("location LIKE ?")
                params.append(f"%{location}%")
            if status and status in ['New', 'Old']:
                conditions.append("json_extract(data, '$.Status') = ?")
                params.append(status)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            c.execute(query, params)
            rows = c.fetchall()
        data = []
        for row in rows:
            place = json.loads(row[0])
            place['Status'] = place.get('Status', 'Old')
            data.append(place)
        for place in scraper.new_results:
            if place['Place ID'] not in {p['Place ID'] for p in data}:
                if (not location or location.lower() in place['Location'].lower()) and (not status or place['Status'] == status):
                    data.append(place)
        df = pd.DataFrame(data)
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ""
        df = df[expected_columns]
        temp_file = os.path.join(tempfile.gettempdir(), f"autism_services_export_{uuid.uuid4()}.csv")
        logger.info(f"Creating temporary CSV file: {temp_file}")
        with open(temp_file, 'w', encoding='utf-8') as f:
            df.to_csv(f, index=False)
        try:
            response = send_file(temp_file, as_attachment=True, download_name="autism_services_export.csv")
            return response
        finally:
            time.sleep(0.1)
            try:
                os.remove(temp_file)
                logger.info(f"Deleted temporary CSV file: {temp_file}")
            except Exception as e:
                logger.error(f"Error deleting temp file {temp_file}: {e}")
    except Exception as e:
        logger.error(f"Error in /api/download: {str(e)}")
        socketio.emit('error', {'message': f"Download failed: {str(e)}"}, namespace='/')
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear_data', methods=['POST'])
def api_clear_data():
    try:
        location = request.args.get("location", None)
        with get_db() as conn:
            c = conn.cursor()
            if location:
                c.execute("DELETE FROM places WHERE location LIKE ?", (f"%{location}%",))
            else:
                c.execute("DELETE FROM places")
            conn.commit()
        logger.info(f"Cleared data for location: {location or 'all'}")
        socketio.emit('info', {'message': f"Cleared data for {location or 'all locations'}"}, namespace='/')
        return jsonify({"status": "Data cleared"})
    except Exception as e:
        logger.error(f"Error in /api/clear_data: {str(e)}")
        socketio.emit('error', {'message': f"Clear data failed: {str(e)}"}, namespace='/')
        return jsonify({"error": str(e)}), 500

@app.route('/manage')
def manage():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM places")
        total_places = c.fetchone()[0]
    return render_template("manage.html", total_places=total_places)

# ==================== Keywords API ====================
@app.route('/api/keywords', methods=['GET'])
def api_get_keywords():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT id, keyword, category, active, created_at, last_used FROM search_keywords ORDER BY category, keyword")
            keywords = []
            for row in c.fetchall():
                keywords.append({
                    'id': row[0],
                    'keyword': row[1],
                    'category': row[2],
                    'active': row[3],
                    'created_at': row[4],
                    'last_used': row[5]
                })
        return jsonify(keywords)
    except Exception as e:
        logger.error(f"Error in /api/keywords GET: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/keywords', methods=['POST'])
def api_add_keyword():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()
        category = data.get('category', 'Other')
        
        if not keyword:
            return jsonify({"error": "Keyword is required"}), 400
        
        with get_db() as conn:
            c = conn.cursor()
            created_at = datetime.now().isoformat()
            c.execute("INSERT INTO search_keywords (keyword, category, active, created_at) VALUES (?, ?, 1, ?)",
                     (keyword, category, created_at))
            conn.commit()
            keyword_id = c.lastrowid
        
        logger.info(f"Added keyword: {keyword}")
        return jsonify({"status": "Keyword added", "id": keyword_id})
    except Exception as e:
        logger.error(f"Error in /api/keywords POST: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/keywords/<int:keyword_id>', methods=['PUT'])
def api_update_keyword(keyword_id):
    try:
        data = request.get_json()
        
        with get_db() as conn:
            c = conn.cursor()
            
            if 'active' in data:
                c.execute("UPDATE search_keywords SET active = ? WHERE id = ?", (data['active'], keyword_id))
            
            if 'keyword' in data:
                c.execute("UPDATE search_keywords SET keyword = ? WHERE id = ?", (data['keyword'], keyword_id))
            
            if 'category' in data:
                c.execute("UPDATE search_keywords SET category = ? WHERE id = ?", (data['category'], keyword_id))
            
            conn.commit()
        
        logger.info(f"Updated keyword ID: {keyword_id}")
        return jsonify({"status": "Keyword updated"})
    except Exception as e:
        logger.error(f"Error in /api/keywords PUT: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/keywords/<int:keyword_id>', methods=['DELETE'])
def api_delete_keyword(keyword_id):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM search_keywords WHERE id = ?", (keyword_id,))
            conn.commit()
        
        logger.info(f"Deleted keyword ID: {keyword_id}")
        return jsonify({"status": "Keyword deleted"})
    except Exception as e:
        logger.error(f"Error in /api/keywords DELETE: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==================== Location Hierarchy API ====================
@app.route('/api/locations/countries', methods=['GET'])
def api_get_countries():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places")
            places = [json.loads(row[0]) for row in c.fetchall()]
        
        countries = {}
        for place in places:
            location = place.get('Location', '')
            if location and ' > ' in location:
                parts = location.split(' > ')
                if len(parts) >= 1:
                    country = parts[0]
                    if country not in countries:
                        countries[country] = 0
                    countries[country] += 1
        
        result = [{'name': k, 'count': v} for k, v in countries.items()]
        result.sort(key=lambda x: x['name'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/locations/countries: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/locations/states', methods=['GET'])
def api_get_states():
    try:
        country = request.args.get('country')
        if not country:
            return jsonify({"error": "country parameter required"}), 400
        
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places")
            places = [json.loads(row[0]) for row in c.fetchall()]
        
        states = {}
        for place in places:
            location = place.get('Location', '')
            if location and ' > ' in location:
                parts = location.split(' > ')
                if len(parts) >= 2 and parts[0] == country:
                    state = parts[1]
                    if state not in states:
                        states[state] = 0
                    states[state] += 1
        
        result = [{'name': k, 'count': v} for k, v in states.items()]
        result.sort(key=lambda x: x['name'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/locations/states: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/locations/cities', methods=['GET'])
def api_get_cities_by_state():
    try:
        country = request.args.get('country')
        state = request.args.get('state')
        
        if not country or not state:
            return jsonify({"error": "country and state parameters required"}), 400
        
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places")
            places = [json.loads(row[0]) for row in c.fetchall()]
        
        cities = {}
        for place in places:
            location = place.get('Location', '')
            if location and ' > ' in location:
                parts = location.split(' > ')
                if len(parts) >= 3 and parts[0] == country and parts[1] == state:
                    city = parts[2]
                    if city not in cities:
                        cities[city] = 0
                    cities[city] += 1
        
        result = [{'name': k, 'count': v} for k, v in cities.items()]
        result.sort(key=lambda x: x['name'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/locations/cities: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/locations/places', methods=['GET'])
def api_get_places_by_location():
    try:
        country = request.args.get('country')
        state = request.args.get('state')
        city = request.args.get('city')
        unsynced_only = request.args.get('unsynced_only', 'false').lower() == 'true'
        
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT place_id, data, wp_synced FROM places")
            rows = c.fetchall()
        
        places = []
        for row in rows:
            place_id = row[0]
            place_data = json.loads(row[1])
            wp_synced = row[2]
            location = place_data.get('Location', '')
            
            # Match location filters
            if location and ' > ' in location:
                parts = location.split(' > ')
                match = True
                
                if country and (len(parts) < 1 or parts[0] != country):
                    match = False
                if state and (len(parts) < 2 or parts[1] != state):
                    match = False
                if city and (len(parts) < 3 or parts[2] != city):
                    match = False
                
                if match:
                    if unsynced_only and wp_synced == 1:
                        continue
                    
                    places.append({
                        'place_id': place_id,
                        'title': place_data.get('Title', 'Unknown'),
                        'category': place_data.get('Category', ''),
                        'address': place_data.get('Google Address', ''),
                        'location': location,
                        'wp_synced': wp_synced,
                        'phone': place_data.get('Phone', ''),
                        'website': place_data.get('Website', '')
                    })
        
        return jsonify(places)
    except Exception as e:
        logger.error(f"Error in /api/locations/places: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==================== Cities API (Legacy) ====================
@app.route('/api/cities', methods=['GET'])
def api_get_cities():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places")
            places = [json.loads(row[0]) for row in c.fetchall()]
        
        cities_dict = {}
        for place in places:
            location = place.get('Location', '')
            if location and ' > ' in location:
                parts = location.split(' > ')
                if len(parts) >= 3:
                    country, state, city = parts[0], parts[1], parts[2]
                    key = f"{country}|{state}|{city}"
                    if key not in cities_dict:
                        cities_dict[key] = {
                            'country': country,
                            'state': state,
                            'city': city,
                            'location': location,
                            'count': 0
                        }
                    cities_dict[key]['count'] += 1
        
        cities = list(cities_dict.values())
        cities.sort(key=lambda x: (x['country'], x['state'], x['city']))
        
        return jsonify(cities)
    except Exception as e:
        logger.error(f"Error in /api/cities: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==================== WordPress Sync Helpers ====================
def convert_business_hours_to_json(business_hours_str):
    """Convert pipe-separated business hours to JSON format"""
    if not business_hours_str:
        return {}
    
    hours_json = {}
    try:
        days = business_hours_str.split('|')
        for day_entry in days:
            parts = day_entry.split(',')
            if len(parts) == 3:
                day, open_time, close_time = parts
                hours_json[day] = {
                    "open": open_time,
                    "close": close_time
                }
    except Exception as e:
        logger.error(f"Error converting business hours: {e}")
    
    return hours_json

def convert_place_to_wordpress_format(place):
    """Convert scraper format to WordPress ListingPro format"""
    # Parse location
    location_parts = []
    if place.get('Location') and ' > ' in place['Location']:
        location_parts = place['Location'].split(' > ')
    
    # Convert business hours
    business_hours_json = convert_business_hours_to_json(place.get('Business Hours (Day,OpenTime,CloseTime)', ''))
    
    # Parse gallery
    gallery_images = []
    if place.get('Gallery'):
        gallery_images = [img.strip() for img in place['Gallery'].split(',') if img.strip()][:10]
    
    # Parse features and tags
    features = []
    if place.get('Features'):
        features = [f.strip() for f in place['Features'].split(',') if f.strip()]
    
    tags = []
    if place.get('Tags (Keywords)'):
        tags = [t.strip() for t in place['Tags (Keywords)'].split(',') if t.strip()]
    
    # Build WordPress payload
    wp_data = {
        "title": place.get('Title', ''),
        "description": place.get('Description', ''),
        "tagline_text": place.get('Tagline', ''),
        "phone": place.get('Phone', ''),
        "email": place.get('Email', ''),
        "website": place.get('Website', ''),
        "gAddress": place.get('Google Address', ''),
        "latitude": str(place.get('Latitude', '')),
        "longitude": str(place.get('Longitude', '')),
        "facebook": place.get('Facebook', ''),
        "twitter": place.get('Twitter', ''),
        "instagram": place.get('Instagram', ''),
        "linkedin": place.get('Linkedin', ''),
        "youtube": place.get('Youtube', ''),
        "video": place.get('Youtube Video URL', ''),
        "price_status": place.get('Price Status ($-moderate)', ''),
        "list_price": place.get('Price From', ''),
        "list_price_to": place.get('Price To', ''),
        "claimed_section": place.get('Claim Status', ''),
        "categories": [place.get('Category', 'Autism Services')] if place.get('Category') else ['Autism Services'],
        "features": features,
        "tags": tags,
        "locations": location_parts if len(location_parts) >= 3 else [],
        "business_hours": business_hours_json,
        "logo_url": place.get('Logo Image', ''),
        "featured_image": place.get('Banner Image', ''),
        "gallery_images": gallery_images,
        "status": "publish"
    }
    
    return wp_data

def check_existing_in_wordpress(place, wp_url, api_key):
    """Check if a listing already exists in WordPress"""
    try:
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Use GET /wp-json/listingpro/v1/listings to get all listings
        listings_url = f"{wp_url.rstrip('/')}/wp-json/listingpro/v1/listings"
        response = requests.get(listings_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Handle different response formats
            if isinstance(data, dict):
                # Format: {"success":true, "listings":[...]} or {"data":[...]}
                listings = data.get('listings', data.get('data', []))
            elif isinstance(data, list):
                listings = data
            else:
                listings = []
            
            # Search for matching listing by title, phone, or address
            place_title = place.get('Title', '').strip().lower()
            place_phone = place.get('Phone', '').strip()
            place_address = place.get('Google Address', '').strip().lower()
            
            for listing in listings:
                # Check by title (most reliable)
                listing_title = listing.get('title', '').strip().lower()
                if listing_title and place_title and listing_title == place_title:
                    return listing.get('post_id')
                
                # Check by phone
                listing_phone = listing.get('phone', '').strip()
                if listing_phone and place_phone and listing_phone == place_phone:
                    return listing.get('post_id')
                
                # Check by address
                listing_address = listing.get('gAddress', listing.get('address', '')).strip().lower()
                if listing_address and place_address and listing_address == place_address:
                    return listing.get('post_id')
        
        return None
    except Exception as e:
        logger.error(f"Error checking existing listing: {e}")
        return None

def sync_place_to_wordpress(place, wp_url, api_key, sync_mode='skip'):
    """
    Sync a single place to WordPress
    
    sync_mode options:
    - 'skip': Skip if exists (safest)
    - 'update': Update if exists, create if not
    - 'force': Always create new (may duplicate)
    """
    try:
        wp_data = convert_place_to_wordpress_format(place)
        
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        api_endpoint = f"{wp_url.rstrip('/')}/wp-json/listingpro/v1/listing"
        
        # Check if listing exists (unless force mode)
        existing_post_id = None
        if sync_mode != 'force':
            existing_post_id = check_existing_in_wordpress(place, wp_url, api_key)
        
        if existing_post_id:
            if sync_mode == 'skip':
                logger.info(f"Skipping existing listing: {place.get('Title')} (WordPress ID: {existing_post_id})")
                return {'status': 'skipped', 'wp_post_id': existing_post_id, 'action': 'skipped'}
            elif sync_mode == 'update':
                # Update existing listing using PUT /wp-json/listingpro/v1/listing/{id}
                update_url = f"{api_endpoint}/{existing_post_id}"
                response = requests.put(update_url, json=wp_data, headers=headers, timeout=30)
                response.raise_for_status()
                logger.info(f"Updated listing: {place.get('Title')} (WordPress ID: {existing_post_id})")
                return {'status': 'success', 'wp_post_id': existing_post_id, 'action': 'updated'}
        
        # Create new listing using POST /wp-json/listingpro/v1/listing
        response = requests.post(api_endpoint, json=wp_data, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        # API returns post_id in response
        wp_post_id = result.get('post_id')
        if not wp_post_id and result.get('success'):
            # Try alternative response format
            wp_post_id = result.get('id')
        
        logger.info(f"Created listing: {place.get('Title')} (WordPress ID: {wp_post_id})")
        
        return {'status': 'success', 'wp_post_id': wp_post_id, 'action': 'created'}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"WordPress API error: {e}")
        return {'status': 'error', 'error': str(e)}
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return {'status': 'error', 'error': str(e)}

def sync_bulk_to_wordpress(places, wp_url, api_key, sync_mode='skip'):
    """
    Sync multiple places to WordPress using bulk endpoint
    
    Uses: POST /wp-json/listingpro/v1/listings/bulk
    """
    try:
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Convert all places to WordPress format
        wp_listings = []
        for place in places:
            wp_data = convert_place_to_wordpress_format(place)
            wp_listings.append(wp_data)
        
        # Use bulk endpoint
        bulk_endpoint = f"{wp_url.rstrip('/')}/wp-json/listingpro/v1/listings/bulk"
        response = requests.post(bulk_endpoint, json={'listings': wp_listings}, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Bulk sync completed: {len(places)} listings")
        
        return {'status': 'success', 'result': result}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"WordPress bulk API error: {e}")
        return {'status': 'error', 'error': str(e)}
    except Exception as e:
        logger.error(f"Bulk sync error: {e}")
        return {'status': 'error', 'error': str(e)}

# ==================== WordPress Sync API ====================
@app.route('/api/wordpress/sync-status', methods=['GET'])
def api_wordpress_sync_status():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM places")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM places WHERE wp_synced = 1")
            synced = c.fetchone()[0]
        
        return jsonify({
            'total': total,
            'synced': synced,
            'unsynced': total - synced
        })
    except Exception as e:
        logger.error(f"Error in /api/wordpress/sync-status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordpress/sync-single', methods=['POST'])
def api_wordpress_sync_single():
    try:
        data = request.get_json()
        place_id = data.get('place_id')
        wp_url = data.get('wp_url')
        api_key = data.get('api_key')
        sync_mode = data.get('sync_mode', 'skip')
        
        if not place_id or not wp_url or not api_key:
            return jsonify({"error": "place_id, wp_url, and api_key are required"}), 400
        
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM places WHERE place_id = ?", (place_id,))
            row = c.fetchone()[0]
            if not row:
                return jsonify({"error": "Place not found"}), 404
            
            place = json.loads(row[0])
        
        # Sync to WordPress
        result = sync_place_to_wordpress(place, wp_url, api_key, sync_mode)
        
        if result['status'] == 'success' or result['status'] == 'skipped':
            # Update sync status in database
            with get_db() as conn:
                c = conn.cursor()
                sync_date = datetime.now().isoformat()
                c.execute("UPDATE places SET wp_synced = 1, wp_post_id = ?, wp_sync_date = ? WHERE place_id = ?",
                         (result['wp_post_id'], sync_date, place_id))
                conn.commit()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/wordpress/sync-single: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordpress/sync-bulk', methods=['POST'])
def api_wordpress_sync_bulk():
    try:
        data = request.get_json()
        wp_url = data.get('wp_url')
        api_key = data.get('api_key')
        location = data.get('location')
        place_ids = data.get('place_ids')  # Array of specific place IDs
        sync_mode = data.get('sync_mode', 'skip')
        use_bulk_endpoint = data.get('use_bulk_endpoint', False)  # Option to use bulk API
        
        if not wp_url or not api_key:
            return jsonify({"error": "wp_url and api_key are required"}), 400
        
        # Get places to sync
        with get_db() as conn:
            c = conn.cursor()
            
            if place_ids:
                # Sync specific places by ID
                placeholders = ','.join('?' * len(place_ids))
                c.execute(f"SELECT place_id, data FROM places WHERE place_id IN ({placeholders})", place_ids)
            elif location:
                # Sync by location (unsynced only)
                c.execute("SELECT place_id, data FROM places WHERE wp_synced = 0 AND location LIKE ?", (f"%{location}%",))
            else:
                # Sync all unsynced
                c.execute("SELECT place_id, data FROM places WHERE wp_synced = 0")
            
            rows = c.fetchall()
        
        if len(rows) == 0:
            return jsonify({
                'total': 0,
                'synced': 0,
                'skipped': 0,
                'failed': 0,
                'errors': []
            })
        
        # If use_bulk_endpoint is True and sync_mode is not 'update', try bulk endpoint
        # Note: Bulk endpoint typically only supports creating new listings
        if use_bulk_endpoint and sync_mode != 'update':
            places = [json.loads(row[1]) for row in rows]
            bulk_result = sync_bulk_to_wordpress(places, wp_url, api_key, sync_mode)
            
            if bulk_result['status'] == 'success':
                # Update all places as synced
                with get_db() as conn:
                    c = conn.cursor()
                    sync_date = datetime.now().isoformat()
                    for row in rows:
                        place_id = row[0]
                        c.execute("UPDATE places SET wp_synced = 1, wp_sync_date = ? WHERE place_id = ?",
                                 (sync_date, place_id))
                    conn.commit()
                
                return jsonify({
                    'total': len(rows),
                    'synced': len(rows),
                    'skipped': 0,
                    'failed': 0,
                    'errors': [],
                    'method': 'bulk_endpoint'
                })
            else:
                # Fall back to individual sync if bulk fails
                logger.warning(f"Bulk endpoint failed, falling back to individual sync: {bulk_result.get('error')}")
        
        # Individual sync (one by one) - original method
        results = {
            'total': len(rows),
            'synced': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'method': 'individual'
        }
        
        for row in rows:
            place_id = row[0]
            place = json.loads(row[1])
            
            # Sync to WordPress
            result = sync_place_to_wordpress(place, wp_url, api_key, sync_mode)
            
            if result['status'] == 'success':
                # Update database
                with get_db() as conn:
                    c = conn.cursor()
                    sync_date = datetime.now().isoformat()
                    c.execute("UPDATE places SET wp_synced = 1, wp_post_id = ?, wp_sync_date = ? WHERE place_id = ?",
                             (result['wp_post_id'], sync_date, place_id))
                    conn.commit()
                
                if result.get('action') == 'created':
                    results['synced'] += 1
                elif result.get('action') == 'updated':
                    results['synced'] += 1
            elif result['status'] == 'skipped':
                results['skipped'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'place': place.get('Title'),
                    'error': result.get('error')
                })
            
            time.sleep(0.5)  # Rate limiting
            
            # Emit progress via WebSocket
            if socketio:
                socketio.emit('sync_progress', {
                    'completed': results['synced'] + results['skipped'] + results['failed'],
                    'total': results['total'],
                    'place': place.get('Title')
                }, namespace='/')
        
        logger.info(f"Bulk sync completed: {results['synced']} synced, {results['skipped']} skipped, {results['failed']} failed")
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in /api/wordpress/sync-bulk: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)