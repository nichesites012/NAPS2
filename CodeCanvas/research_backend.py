#!/usr/bin/env python3
"""
Async Domain Research Backend
Extracted from the original domain research script with improvements
"""

import os
import asyncio
import json
import urllib.parse
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from dateutil import parser as date_parser
from dotenv import load_dotenv

import aiohttp

# Load environment variables from .env file
load_dotenv()


@dataclass
class DomainData:
    """Data class for domain information"""
    keyword: str
    domain: str
    creation_date: str
    age_days: int
    status: str
    google_string: str = ""
    age_display: str = ""  # Human-readable age (e.g., "5 years, 123 days")


class AsyncDomainResearcher:
    """Asynchronous domain research backend"""
    
    def __init__(self, serp_api_key: str = None, whois_api_key: str = None):
        # Get API keys from environment variables or parameters, with fallback defaults
        self.serp_api_key = (serp_api_key or 
                           os.getenv('SERP_API_KEY', '') or 
                           "63cc73fca4mshf55eb3b0811d360p14620ajsn92730fc828bc")
        self.whois_api_key = (whois_api_key or 
                            os.getenv('WHOIS_API_KEY', '') or 
                            "653b90312dmsh9219d00db599bf4p1e3706jsn8f0ba5f7b11b")
        
        # API hosts
        self.serp_host = "google-search116.p.rapidapi.com"
        self.whois_host = "whois-api6.p.rapidapi.com"
        
        # Session for HTTP requests
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def search_google(self, keyword: str) -> Optional[Dict]:
        """Search Google using RapidAPI SERP with US localization"""
        if not self.serp_api_key:
            raise ValueError("SERP API key is required")
            
        try:
            encoded_query = urllib.parse.quote_plus(keyword)
            url = f"https://{self.serp_host}/?query={encoded_query}&gl=US"
            
            headers = {
                'x-rapidapi-key': self.serp_api_key,
                'x-rapidapi-host': self.serp_host
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # Rate limited, wait and retry once
                    await asyncio.sleep(2)
                    async with self.session.get(url, headers=headers) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            print(f"Search API retry failed for '{keyword}': {retry_response.status}")
                            return None
                else:
                    print(f"Search API error for '{keyword}': {response.status}")
                    return None
        except asyncio.TimeoutError:
            print(f"Timeout searching for '{keyword}'")
            return None
        except Exception as e:
            print(f"Error searching for '{keyword}': {e}")
            return None
    
    def extract_domains(self, search_results: Dict) -> set:
        """Extract and convert URLs to domain level"""
        domains = set()
        
        if not search_results:
            return domains
        
        try:
            urls = []
            
            # Check for organic results
            if 'results' in search_results:
                for result in search_results['results']:
                    if 'url' in result:
                        urls.append(result['url'])
                    elif 'link' in result:
                        urls.append(result['link'])
            
            # Check for other possible structures
            if 'organic' in search_results:
                for result in search_results['organic']:
                    if 'url' in result:
                        urls.append(result['url'])
            
            # Extract domains from URLs
            for url in urls:
                try:
                    parsed = urllib.parse.urlparse(url)
                    domain = parsed.netloc.lower()
                    
                    # Remove www. prefix
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    # Only add valid domains
                    if domain and '.' in domain and not domain.startswith('.'):
                        domains.add(domain)
                except Exception:
                    continue
            
            return domains
        except Exception as e:
            print(f"Error extracting domains: {e}")
            return domains
    
    async def get_whois_data(self, domain: str) -> Optional[Dict]:
        """Get WHOIS data using RapidAPI with the working endpoint"""
        if not self.whois_api_key:
            raise ValueError("WHOIS API key is required")
            
        # Use the working WHOIS endpoint
        url = f"https://{self.whois_host}/whois/api/v1/getData"
        headers = {
            'x-rapidapi-key': self.whois_api_key,
            'x-rapidapi-host': self.whois_host,
            'Content-Type': "application/json"
        }
        payload = json.dumps({"query": domain})
        
        # Retry with exponential backoff
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(url, headers=headers, data=payload) as response:
                    if response.status == 200:
                        print(f"Successfully retrieved WHOIS data for: {domain}")
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            print(f"Rate limited for '{domain}', waiting {delay}s before retry {attempt + 1}/{max_retries}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            print(f"WHOIS API rate limit exceeded for '{domain}' after {max_retries} retries")
                            return None
                    elif response.status == 403:
                        print(f"WHOIS API access forbidden for '{domain}' - check API key permissions")
                        return None
                    else:
                        text = await response.text()
                        print(f"WHOIS API error for '{domain}': {response.status} - {text[:100]}")
                        return None
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    print(f"Timeout for '{domain}', retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"Timeout getting WHOIS data for '{domain}' after {max_retries} retries")
                    return None
            except Exception as e:
                print(f"Error getting WHOIS data for '{domain}': {e}")
                return None
        
        return None
    
    def calculate_domain_age(self, whois_data: Dict) -> Tuple[Optional[str], Optional[int]]:
        """Calculate domain age from creation_date with flexible parsing for new API format"""
        if not whois_data or 'result' not in whois_data:
            return None, None
        
        try:
            result = whois_data['result']
            creation_date_raw = result.get('creation_date')
            
            if not creation_date_raw:
                return None, None
            
            # Handle case where creation_date might be a list or string
            creation_date_str = None
            if isinstance(creation_date_raw, list):
                # Take the first element from the list
                creation_date_str = creation_date_raw[0] if creation_date_raw else None
            else:
                # If it's a string, use it directly
                creation_date_str = creation_date_raw
            
            if not creation_date_str:
                return None, None
            
            # Use dateutil for flexible date parsing
            try:
                creation_date = date_parser.parse(creation_date_str)
            except Exception:
                # Fallback to manual parsing for formats like "1997-09-15 04:00:00"
                try:
                    creation_date = datetime.strptime(creation_date_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    try:
                        # Try without time
                        creation_date = datetime.strptime(creation_date_str, "%Y-%m-%d")
                    except Exception:
                        print(f"Could not parse creation date: {creation_date_str}")
                        return None, None
            
            current_date = datetime.now()
            
            # Make creation_date timezone-naive for comparison
            if creation_date.tzinfo is not None:
                creation_date = creation_date.replace(tzinfo=None)
            
            # Calculate age in days
            age_delta = current_date - creation_date
            age_days = age_delta.days
            
            # Calculate years and remaining days for better display
            age_years = age_days // 365
            remaining_days = age_days % 365
            
            # Format creation date for display
            formatted_date = creation_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Create a descriptive age string
            if age_years > 0:
                age_description = f"{age_years} years, {remaining_days} days"
                print(f"Domain created: {formatted_date}, Age: {age_days} days ({age_description})")
            else:
                print(f"Domain created: {formatted_date}, Age: {age_days} days")
            
            return formatted_date, age_days
            
        except Exception as e:
            print(f"Error calculating domain age: {e}")
            return None, None
    
    async def process_domain(self, domain: str, keyword: str) -> DomainData:
        """Process a single domain asynchronously"""
        try:
            # Get WHOIS data
            whois_data = await self.get_whois_data(domain)
            
            if not whois_data:
                return DomainData(keyword, domain, "N/A", -1, "WHOIS Failed")
            
            # Calculate domain age
            creation_date, age_days = self.calculate_domain_age(whois_data)
            
            if creation_date and age_days is not None:
                # Calculate age display string
                age_years = age_days // 365
                remaining_days = age_days % 365
                
                if age_years > 0:
                    age_display = f"{age_years} years, {remaining_days} days"
                else:
                    age_display = f"{age_days} days"
                
                return DomainData(keyword, domain, creation_date, age_days, "Success", "", age_display)
            else:
                return DomainData(keyword, domain, "N/A", -1, "Age Calculation Failed")
        except Exception as e:
            return DomainData(keyword, domain, "N/A", -1, f"Error: {str(e)}")
    
    async def research_keywords(self, keywords: List[str], max_domains_per_keyword: int = 5,
                              progress_callback=None, domain_progress_callback=None, 
                              cancelled_event=None) -> List[DomainData]:
        """Research multiple keywords and return results"""
        results = []
        total_keywords = len(keywords)
        
        # Create semaphore to limit concurrent domain requests (reduced from 5 to 2)
        domain_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent domain requests
        
        async def process_domain_with_semaphore(domain, keyword):
            """Process domain with concurrency control and cancellation check"""
            # Check for cancellation before processing
            if cancelled_event and cancelled_event.is_set():
                raise asyncio.CancelledError("Task cancelled")
                
            async with domain_semaphore:
                result = await self.process_domain(domain, keyword)
                if domain_progress_callback:
                    await domain_progress_callback()
                # Add small delay between domain requests to be more respectful
                await asyncio.sleep(0.5)
                return result
        
        for i, keyword in enumerate(keywords):
            try:
                # Check for cancellation at start of each keyword
                if cancelled_event and cancelled_event.is_set():
                    raise asyncio.CancelledError("Task cancelled")
                
                # Update progress
                if progress_callback:
                    await progress_callback(i, total_keywords, f"Processing keyword: {keyword}")
                
                # Search Google
                search_results = await self.search_google(keyword)
                
                # Check for cancellation after search
                if cancelled_event and cancelled_event.is_set():
                    raise asyncio.CancelledError("Task cancelled")
                
                if not search_results:
                    result = DomainData(keyword, "N/A", "N/A", -1, "Search Failed")
                    results.append(result)
                    continue
                
                # Extract domains
                domains = self.extract_domains(search_results)
                
                if not domains:
                    result = DomainData(keyword, "N/A", "N/A", -1, "No Domains Found")
                    results.append(result)
                    continue
                
                # Process domains concurrently with semaphore
                domain_tasks = []
                for domain in list(domains)[:max_domains_per_keyword]:
                    # Check for cancellation before creating each domain task
                    if cancelled_event and cancelled_event.is_set():
                        raise asyncio.CancelledError("Task cancelled")
                    task = process_domain_with_semaphore(domain, keyword)
                    domain_tasks.append(task)
                
                # Wait for all domain tasks to complete
                if domain_tasks:
                    try:
                        domain_results = await asyncio.gather(*domain_tasks, return_exceptions=True)
                        
                        for result in domain_results:
                            if isinstance(result, DomainData):
                                results.append(result)
                            elif isinstance(result, asyncio.CancelledError):
                                # Re-raise cancellation
                                raise result
                            elif isinstance(result, Exception):
                                error_result = DomainData(keyword, "N/A", "N/A", -1, f"Error: {str(result)}")
                                results.append(error_result)
                    except asyncio.CancelledError:
                        # Cancel any remaining tasks
                        for task in domain_tasks:
                            if not task.done():
                                task.cancel()
                        raise
                
                # Check for cancellation before delay
                if cancelled_event and cancelled_event.is_set():
                    raise asyncio.CancelledError("Task cancelled")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                # Re-raise cancellation to be handled at the app level
                raise
            except Exception as e:
                error_result = DomainData(keyword, "N/A", "N/A", -1, f"Keyword Error: {str(e)}")
                results.append(error_result)
        
        # Final progress update (only if not cancelled)
        if progress_callback and (not cancelled_event or not cancelled_event.is_set()):
            await progress_callback(total_keywords, total_keywords, "Research completed!")
        
        return results


def apply_advanced_filter(results: List[DomainData], min_age: int, max_age: int, 
                         min_domains: int) -> List[DomainData]:
    """Apply advanced filtering to results"""
    # Group results by keyword
    keyword_groups = {}
    for result in results:
        if result.keyword not in keyword_groups:
            keyword_groups[result.keyword] = []
        keyword_groups[result.keyword].append(result)
    
    # Filter based on criteria
    filtered_results = []
    for keyword, keyword_results in keyword_groups.items():
        # Count domains within age range
        valid_domains = [
            r for r in keyword_results 
            if r.age_days != -1 and min_age <= r.age_days <= max_age
        ]
        
        # Only include if minimum domain count is met
        if len(valid_domains) >= min_domains:
            filtered_results.extend(valid_domains)
    
    return filtered_results