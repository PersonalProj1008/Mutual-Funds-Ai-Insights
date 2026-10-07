import io
import requests
import pandas as pd
from bs4 import BeautifulSoup

class MarketCaptureScraper:
    def __init__(self):
        self.url = "https://www.advisorkhoj.com/mutual-funds-research/market-capture-ratio"
        self.session = requests.Session()
        # Pretend to be a standard web browser to avoid getting blocked
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        })

    def fetch_ratios(self, category_value, scheme_value, period="3"):
        # 1. Fetch the initial page to get any session cookies or hidden form tokens (like CSRF)
        res = self.session.get(self.url)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        payload = {}
        # Find the form and extract all hidden security tokens
        form = soup.find('form') 
        if form:
            for hidden in form.find_all("input", type="hidden"):
                if hidden.get("name"):
                    payload[hidden.get("name")] = hidden.get("value")
                    
        # 2. Inject our target data into the payload
        # NOTE: You must verify these exact field names (e.g., 'category', 'scheme') 
        # by inspecting the Network tab in your browser when you manually submit the form.
        payload['category'] = category_value  
        payload['scheme'] = scheme_value      
        payload['period'] = period            

        # 3. Submit the form
        post_res = self.session.post(self.url, data=payload)
        
        # 4. Parse the results using Pandas (the easiest way to extract HTML tables)
        # We wrap the HTML string in io.StringIO to avoid Pandas warnings
        try:
            tables = pd.read_html(io.StringIO(post_res.text))
            
            # Loop through the tables on the page to find the one with our ratios
            for df in tables:
                # Check if this table contains the columns we care about
                if "Capture Ratio" in df.columns or "Up Market Capture Ratio (%)" in df.values:
                    # Convert the matching table to a dictionary
                    return df.to_dict(orient='records')
                    
        except ValueError:
            print("No tables found in the HTML response.")
            return None

    def get_categories(self):
            """
            Scrapes the AdvisorKhoj page to get all available mutual fund categories.
            Returns a list of dictionaries: [{'value': '...', 'label': '...'}, ...]
            """
            res = self.session.get(self.url)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            categories = []
            
            # Locate the category dropdown. 
            # Inspect the page source to confirm the exact ID or name (usually name="category")
            category_select = soup.find('select', {'id': 'sel_schemeCategories'}) 
            
            if category_select:
                # Loop through all options inside the dropdown
                for option in category_select.find_all('option'):
                    val = option.get('value')
                    label = option.text.strip()
                    
                    # Skip the placeholder option (like "Select Category" or empty value)
                    if val and val.strip() != "":
                        categories.append({
                            "value": val,
                            "label": label
                        })
                        
            return categories

    def suggest_funds(self, query, category="Equity: Large Cap"):
            """
            Fetches scheme name suggestions based on a search query and a selected category.
            
            Args:
                query (str): The text the user is typing (e.g., "Mirae" or "M")
                category (str): The default category to search within.
                
            Returns:
                list: A list of matching fund names (strings).
            """
            ajax_url = "https://www.advisorkhoj.com/mutual-funds-research/autoSuggestAllMfSchemesShortNames"
            
            payload = {
                'query': query,
                'category': category
            }
            
            try:
                res = self.session.post(ajax_url, data=payload)
                
                # The server returns a clean JSON list of strings, 
                # exactly as you saw in the Network Preview tab.
                suggestions = res.json()
                
                return suggestions
                
            except Exception as e:
                print(f"Error fetching suggestions for '{query}': {e}")
                return []





#  --------- E X A M P L E   U S A G E ---------

if __name__ == "__main__":
    scraper = MarketCaptureScraper()
    
    # Get all categories available
    all_categories = scraper.get_categories()
    print(all_categories[:3])

    # Get Fund Scheme name suggestions
    results = scraper.suggest_funds(query="Mir", category="Equity: Large Cap")
    print(results)


    # Get the ratios
    data = scraper.fetch_ratios(
        category_value="Equity: Large Cap", 
        scheme_value="Mirae Asset Large Cap Gr", 
        period="5"
    )

    print(data)


#  Output data formats are as follows:

# [{'value': 'Equity: Contra', 'label': 'Equity: Contra'}, {'value': 'Equity: Dividend Yield', 'label': 'Equity: Dividend Yield'}, {'value': 'Equity: ELSS', 'label': 'Equity: ELSS'}]
# ['Mirae Asset Large Cap Dir Gr', 'Mirae Asset Large Cap Gr']
# [{'Scheme Name': 'Mirae Asset Large Cap Gr', 'AMC Name': 'MiraeMF', 'Benchmark Name': 'Nifty 100 TRI', 'Launch Date': '01-04-2008', 'Scheme Return (%)': 6.03, 'Up Market Capture Ratio (%)': 90.0, 'Down Market Capture Ratio (%)': 94.0, 'Capture Ratio': 0.96}]