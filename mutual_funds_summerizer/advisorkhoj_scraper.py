import requests
from bs4 import BeautifulSoup
import pandas as pd
import io

class FundDataError(Exception):
    """Custom exception raised when fund data is unavailable for the selected period."""
    pass

class MarketCaptureScraper:
    def __init__(self):
        self.url = "https://www.advisorkhoj.com/mutual-funds-research/market-capture-ratio"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_ratios(self, category_value, scheme_value, period="3"):
        res = self.session.get(self.url)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        payload = {}
        form = soup.find('form') 
        if form:
            for hidden in form.find_all("input", type="hidden"):
                if hidden.get("name"):
                    payload[hidden.get("name")] = hidden.get("value")
                    
        payload['category'] = category_value  
        payload['scheme'] = scheme_value      
        payload['period'] = period            

        post_res = self.session.post(self.url, data=payload)
        
        try:
            tables = pd.read_html(io.StringIO(post_res.text))
            
            for df in tables:
                if "Capture Ratio" in df.columns or "Up Market Capture Ratio (%)" in df.values:
                    records = df.to_dict(orient='records')
                    
                    # Ensure we grab the actual fund, not the benchmark/category average row
                    for row in records:
                        row_scheme_name = str(row.get('Scheme Name', ''))
                        if scheme_value.lower() in row_scheme_name.lower():
                            return row # Returns the single dict directly
                            
                    # Table exists, but the fund row is missing
                    raise FundDataError(
                        f"'{scheme_value}' was found, but lacks market capture data. "
                        f"It likely hasn't been active for a full {period}-year period."
                    )
            
            # Form submitted successfully, but no matching tables were rendered
            raise FundDataError(
                f"No capture ratio data generated for '{scheme_value}'. "
                f"Verify the fund has at least {period} years of market history."
            )
            
        except ValueError:
            # pd.read_html throws ValueError if 0 tables are found in the HTML
            raise FundDataError(
                f"Failed to retrieve data for '{scheme_value}'. "
                f"The fund likely does not have a {period}-year track record."
            )

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

# ########################################################
#  Output data formats are as follows:
# ########################################################

# [{'value': 'Equity: Contra', 'label': 'Equity: Contra'}, {'value': 'Equity: Dividend Yield', 'label': 'Equity: Dividend Yield'}, {'value': 'Equity: ELSS', 'label': 'Equity: ELSS'}]
# ['Mirae Asset Large Cap Dir Gr', 'Mirae Asset Large Cap Gr']
# [{'Scheme Name': 'Mirae Asset Large Cap Gr', 'AMC Name': 'MiraeMF', 'Benchmark Name': 'Nifty 100 TRI', 'Launch Date': '01-04-2008', 'Scheme Return (%)': 6.03, 'Up Market Capture Ratio (%)': 90.0, 'Down Market Capture Ratio (%)': 94.0, 'Capture Ratio': 0.96}]