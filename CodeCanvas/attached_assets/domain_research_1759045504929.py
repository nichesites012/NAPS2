#!/usr/bin/env python3
"""
Domain Age Research Script
Reads keywords from k.txt, searches Google, extracts domains, and analyzes domain age
"""

import http.client
import json
import csv
import urllib.parse
from datetime import datetime
import re
import time

class DomainResearcher:
    def __init__(self):
        # API Keys from user
        self.serp_api_key = "f8d42cd1a2mshc05199ca35d2387p1775a4jsn0351186289bf"
        self.whois_api_key = "63cc73fca4mshf55eb3b0811d360p14620ajsn92730fc828bc"
        
        # API hosts
        self.serp_host = "google-search116.p.rapidapi.com"
        self.whois_host = "whois-api6.p.rapidapi.com"
        
        # CSV file setup
        self.csv_file = "domain_analysis.csv"
        self.setup_csv()
        
    def setup_csv(self):
        """Initialize CSV file with headers"""
        try:
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Keyword', 'Domain', 'Creation_Date', 'Domain_Age_Days', 'Status'])
            print(f"CSV file '{self.csv_file}' initialized successfully")
        except Exception as e:
            print(f"Error setting up CSV file: {e}")
            
    def read_keywords(self, filename='k.txt'):
        """Read keywords from k.txt file"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                keywords = [line.strip() for line in file if line.strip()]
            print(f"Successfully read {len(keywords)} keywords from {filename}")
            return keywords
        except FileNotFoundError:
            print(f"Error: {filename} not found. Please create the file with keywords.")
            return []
        except Exception as e:
            print(f"Error reading keywords: {e}")
            return []
            
    def search_google(self, keyword):
        """Search Google using RapidAPI SERP with US localization"""
        try:
            conn = http.client.HTTPSConnection(self.serp_host)
            
            # URL encode the query and add gl=US for US localization
            encoded_query = urllib.parse.quote_plus(keyword)
            
            headers = {
                'x-rapidapi-key': self.serp_api_key,
                'x-rapidapi-host': self.serp_host
            }
            
            # Make request with US localization
            conn.request("GET", f"/?query={encoded_query}&gl=US", headers=headers)
            
            res = conn.getresponse()
            data = res.read()
            conn.close()
            
            if res.status == 200:
                response_data = json.loads(data.decode("utf-8"))
                print(f"Successfully searched for keyword: {keyword}")
                return response_data
            else:
                print(f"Search API error for '{keyword}': {res.status}")
                return None
                
        except Exception as e:
            print(f"Error searching for '{keyword}': {e}")
            return None
            
    def extract_domains(self, search_results):
        """Extract and convert URLs to domain level"""
        domains = set()
        
        if not search_results:
            return domains
            
        try:
            # Look for URLs in different possible response structures
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
                        
                    # Only add valid domains (contains at least one dot)
                    if domain and '.' in domain and not domain.startswith('.'):
                        domains.add(domain)
                        
                except Exception as e:
                    continue
                    
            print(f"Extracted {len(domains)} unique domains")
            return domains
            
        except Exception as e:
            print(f"Error extracting domains: {e}")
            return domains
            
    def get_whois_data(self, domain):
        """Get WHOIS data using RapidAPI"""
        try:
            conn = http.client.HTTPSConnection(self.whois_host)
            
            payload = json.dumps({"query": domain})
            
            headers = {
                'x-rapidapi-key': self.whois_api_key,
                'x-rapidapi-host': self.whois_host,
                'Content-Type': "application/json"
            }
            
            conn.request("POST", "/whois/api/v1/getData", payload, headers)
            
            res = conn.getresponse()
            data = res.read()
            conn.close()
            
            if res.status == 200:
                response_data = json.loads(data.decode("utf-8"))
                print(f"Successfully retrieved WHOIS data for: {domain}")
                return response_data
            else:
                print(f"WHOIS API error for '{domain}': {res.status}")
                return None
                
        except Exception as e:
            print(f"Error getting WHOIS data for '{domain}': {e}")
            return None
            
    def calculate_domain_age(self, whois_data):
        """Calculate domain age from creation_date"""
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
                # If it's a list, take the first element
                creation_date_str = creation_date_raw[0] if creation_date_raw else None
            else:
                # If it's a string, use it directly
                creation_date_str = creation_date_raw
                
            if not creation_date_str:
                return None, None
                
            # Parse creation date (format: "2025-05-23 07:16:28")
            creation_date = datetime.strptime(creation_date_str, "%Y-%m-%d %H:%M:%S")
            current_date = datetime.now()
            
            # Calculate age in days
            age_delta = current_date - creation_date
            age_days = age_delta.days
            
            print(f"Domain created: {creation_date_str}, Age: {age_days} days")
            return creation_date_str, age_days
            
        except Exception as e:
            print(f"Error calculating domain age: {e}")
            return None, None
            
    def save_to_csv(self, keyword, domain, creation_date, age_days, status):
        """Save data to CSV file in real-time"""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([keyword, domain, creation_date, age_days, status])
            print(f"Saved to CSV: {domain} - {age_days} days old")
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            
    def process_keywords(self):
        """Main function to process all keywords"""
        keywords = self.read_keywords()
        
        if not keywords:
            print("No keywords found. Please add keywords to k.txt file.")
            return
            
        total_keywords = len(keywords)
        print(f"Starting processing of {total_keywords} keywords...\n")
        
        for i, keyword in enumerate(keywords, 1):
            print(f"[{i}/{total_keywords}] Processing keyword: '{keyword}'")
            
            # Step 1: Search Google
            search_results = self.search_google(keyword)
            
            if not search_results:
                self.save_to_csv(keyword, "N/A", "N/A", "N/A", "Search Failed")
                continue
                
            # Step 2: Extract domains
            domains = self.extract_domains(search_results)
            
            if not domains:
                self.save_to_csv(keyword, "N/A", "N/A", "N/A", "No Domains Found")
                continue
                
            # Step 3: Process each domain
            for domain in list(domains)[:5]:  # Limit to first 5 domains per keyword
                print(f"  Analyzing domain: {domain}")
                
                # Get WHOIS data
                whois_data = self.get_whois_data(domain)
                
                if not whois_data:
                    self.save_to_csv(keyword, domain, "N/A", "N/A", "WHOIS Failed")
                    continue
                    
                # Calculate domain age
                creation_date, age_days = self.calculate_domain_age(whois_data)
                
                if creation_date and age_days is not None:
                    self.save_to_csv(keyword, domain, creation_date, age_days, "Success")
                else:
                    self.save_to_csv(keyword, domain, "N/A", "N/A", "Age Calculation Failed")
                    
                # Add small delay to avoid rate limiting
                time.sleep(1)
                
            print(f"Completed processing keyword: '{keyword}'\n")
            
        print(f"Processing complete! Results saved to {self.csv_file}")

def main():
    """Main execution function"""
    print("Domain Age Research Script Starting...\n")
    
    researcher = DomainResearcher()
    researcher.process_keywords()
    
    print("\nScript execution completed!")

if __name__ == "__main__":
    main()