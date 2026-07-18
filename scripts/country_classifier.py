import pandas as pd
import pycountry
import re
import matplotlib.pyplot as plt
import seaborn as sns
# Get a list of all country names and their ISO codes using pycountry
COUNTRIES = [country.name for country in pycountry.countries]
COUNTRY_CODES = [country.alpha2 for country in pycountry.countries]
COUNTRY_CODE_MAP = {code: name for code, name in zip(COUNTRY_CODES, COUNTRIES)}

# Add common country abbreviations (e.g., "USA" for "United States")
COUNTRY_CODE_MAP.update({
    "USA": "United States",
    "UK": "United Kingdom",
    "UAE": "United Arab Emirates",
    "HK": "Hong Kong",
    "PRC": "China",
})

# US state codes to avoid confusion with country codes
US_STATE_CODES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
                  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
                  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
                  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

# Map official country names to common variants for output
COMMON_NAMES = {
    "Iran, Islamic Republic of": "Iran",
    "Korea, Republic of": "South Korea",
    "Korea, Democratic People's Republic of": "North Korea",
    "Holy See": "Vatican",
    # Add more as needed
}

# Map common country name variations to official pycountry names
COUNTRY_NAME_VARIANTS = {
    "Iran": "Iran, Islamic Republic of",
    "South Korea": "Korea, Republic of",
    "North Korea": "Korea, Democratic People's Republic of",
    "Vatican": "Holy See",
    # Add more as needed
}

def extract_countries(affiliation):
    """
    Given an affiliation string, extract all unique country names or codes.
    Handles US state codes, country name variations, and outputs common names.
    """
    if not isinstance(affiliation, str):
        return None

    # Split the affiliation string by semicolons to handle multiple affiliations
    affiliations = re.split(r";", affiliation)
    # Deduplicate affiliations by converting to a set and back to a list
    unique_affiliations = list(set(affiliations))
    countries_found = set()

    # Iterate through each unique affiliation
    for affil in unique_affiliations:
        affil = affil.strip()

        # Split the affiliation by commas to isolate potential country mentions
        parts = re.split(r",", affil)

        # Iterate through the parts in reverse order (prioritize the end of the string)
        for part in reversed(parts):
            part_clean = part.strip().upper()

            # Check for US state codes first (e.g., "TN" is Tennessee, not Tunisia)
            if part_clean in US_STATE_CODES:
                countries_found.add("United States")
                break  # Skip further checks for this part

            # Check for country codes (e.g., "USA", "UK")
            for code, name in COUNTRY_CODE_MAP.items():
                if code.upper() == part_clean:
                    countries_found.add(name)
                    break  # Stop searching for this part once a match is found

            # Check for country name variants and official names
            part_stripped = part.strip()
            # Check if the stripped part is a variant
            official_name = COUNTRY_NAME_VARIANTS.get(part_stripped, part_stripped)
            # Check if the official name is in COUNTRIES
            if official_name in COUNTRIES:
                common_name = COMMON_NAMES.get(official_name, official_name)
                countries_found.add(common_name)
                break

            # Case-insensitive check against all country names
            for country in COUNTRIES:
                if country.lower() == part_stripped.lower():
                    common_name = COMMON_NAMES.get(country, country)
                    countries_found.add(common_name)
                    break

    # Return the list of unique countries found
    return list(countries_found) if countries_found else None

def extract_affiliation_country(input_csv, output_csv):
    """
    Reads input CSV, looks for an affiliation column ("Author Affiliations" or "Correspondence Address"),
    extracts countries from the affiliation string, and writes a new CSV with a 'Countries' column.
    """
    df = pd.read_csv(input_csv)

    # Determine which affiliation column to use (if any)
    if 'Author Affiliations' in df.columns:
        affil_col = 'Author Affiliations'
        year='Publication Year'
    elif 'Correspondence Address' in df.columns:
        affil_col = 'Correspondence Address'
        year='Year'
    else:
        print(f"No affiliation column found in {input_csv}. Skipping.")
        return

    # Create a new DataFrame with only the 'Affiliation' and 'Countries' columns
    df_check = pd.DataFrame({
        'Affiliation': df[affil_col],
        'Countries': df[affil_col].apply(extract_countries),
        'Year': df[year]

    })

    # Save the new DataFrame to a CSV file
    df_check.to_csv(output_csv, index=False)
    print(f"Processed {input_csv} -> {output_csv}")

def plot_country_frequency(paths):
    """
    Plots the frequency of countries per year using pie charts or histograms.
    """
    for path in paths:
        input_csv = f"affiliation_country_{path}.csv"
        df = pd.read_csv(input_csv)

        # Explode the 'Countries' column (each row may contain a list of countries)
        df = df.explode('Countries')

        # Group by Year and Countries, then count occurrences
        country_year_counts = df.groupby(['Year', 'Countries']).size().reset_index(name='Count')

        # Plot for each year
        for year, data in country_year_counts.groupby('Year'):
            plt.figure(figsize=(10, 6))
            sns.barplot(x='Count', y='Countries', data=data.nlargest(10, 'Count'), palette='viridis')
            plt.title(f'Top 10 Countries in {year} ({path})')
            plt.xlabel('Count')
            plt.ylabel('Countries')
            plt.tight_layout()
            plt.show()

def plot_country_evolution(paths, top_n=10):
    """
    Plots the evolution of the top N countries over the years using a line chart.
    """
    for path in paths:
        input_csv = f"affiliation_country_{path}.csv"
        df = pd.read_csv(input_csv)

        # Explode the 'Countries' column (each row may contain a list of countries)
        df = df.explode('Countries')

        # Group by Year and Countries, then count occurrences
        country_year_counts = df.groupby(['Year', 'Countries']).size().reset_index(name='Count')

        # Identify the top N countries based on total frequency across all years
        top_countries = country_year_counts.groupby('Countries')['Count'].sum().nlargest(top_n).index

        # Filter the data to include only the top N countries
        filtered_data = country_year_counts[country_year_counts['Countries'].isin(top_countries)]

        # Plot the evolution of the top N countries over the years
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=filtered_data, x='Year', y='Count', hue='Countries', marker='o', palette='tab10')
        plt.title(f'Evolution of Top {top_n} Countries Over Years ({path})')
        plt.xlabel('Year')
        plt.ylabel('Count')
        plt.legend(title='Countries', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        #plt.show()
        plt.savefig(f"affiliation_country_{path}.pdf")


def plot_country_evolution1(paths, top_n=10):
    """
    For each given path, creates a line plot with:
      - X-axis as Year.
      - Y-axis as paper frequency.
      - Each line for one of the top 'top_n' countries.
    """
    for path in paths:
        input_csv = f"affiliation_country_{path}.csv"
        df = pd.read_csv(input_csv)
        
        # Convert the "Countries" column from string representation of a list to an actual list (if needed)
        # This assumes that rows look like "['United States', 'United Kingdom']" in the CSV.
        def parse_countries(x):
            try:
                return ast.literal_eval(x) if pd.notnull(x) else []
            except Exception:
                return [x]  # if conversion fails, return x as a single country string

        df["Countries"] = df["Countries"].apply(parse_countries)
    
        # Create one row per country by exploding the list column
        df = df.explode("Countries")
    
        # Group by Year and Countries to count occurrences
        country_year_counts = df.groupby(["Year", "Countries"]).size().reset_index(name="Count")
    
        # Identify the top N countries across all years
        top_countries = (country_year_counts
                         .groupby("Countries")["Count"]
                         .sum()
                         .nlargest(top_n)
                         .index)
    
        # Filter the data to only include these top countries
        filtered_data = country_year_counts[country_year_counts["Countries"].isin(top_countries)]
    
        # Create the line plot
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=filtered_data, x="Year", y="Count", hue="Countries", 
                     marker="o", palette="tab10")
        plt.title(f"Evolution of Top {top_n} Countries Over Years ({path})")
        plt.xlabel("Year")
        plt.ylabel("Paper Frequency")
        plt.legend(title="Countries", bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        plt.show()
        plt.savefig(f"affiliation_country_{path}.pdf")

def run_all_affiliations():
    paths = ["IEEE", "Pubmed", "Scopus"]
    for path in paths:
        input_csv = f"{path}.csv"
        output_csv = f"affiliation_country_{path}.csv"
        extract_affiliation_country(input_csv, output_csv)


import pandas as pd
import re
import matplotlib.pyplot as plt
import seaborn as sns
import ast
def parse_country_field(country_field):
    """
    Parse the 'Countries' field (likely stored as a string representation of a list) 
    and return the first country (if available).
    """
    try:
        if isinstance(country_field, str):
            parsed = ast.literal_eval(country_field)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[0]
            else:
                return str(parsed)
        elif isinstance(country_field, list):
            return country_field[0]
        else:
            return str(country_field)
    except Exception:
        return str(country_field)

def append_country_institution(inst_str, country):
    """
    For the IEEE (or generic) case: if the country isn't already in the institution label,
    append it.
    """
    if not isinstance(inst_str, str):
        return inst_str
    if country and country.lower() not in inst_str.lower():
        return f"{inst_str} ({country})"
    return inst_str

def simplify_scopus_institution(inst_str, country):
    """
    For Scopus-style strings: use a regex to extract a concise institution
    (e.g., capturing 'University', 'Institute', 'School', etc.) and then append the country.
    """
    if not isinstance(inst_str, str):
        return inst_str
    match = re.search(r'([^,]*\b(?:University|Institute|School|Academy|College)\b[^,]*)', inst_str, re.IGNORECASE)
    if match:
        simplified = match.group(1).strip()
    else:
        simplified = inst_str.split(',')[0].strip()
    if country and country.lower() not in simplified.lower():
        simplified = f"{simplified} ({country})"
    return simplified

def extract_institutions_generic(affiliation):
    """
    Extract institutions from a generic affiliation string by splitting over semicolons
    and then by commas looking for keywords.
    """
    if not isinstance(affiliation, str):
        return None
    institutions = []
    affiliation_parts = [part.strip() for part in affiliation.split(';') if part.strip()]
    for part in affiliation_parts:
        segments = [seg.strip() for seg in part.split(',') if seg.strip()]
        found = None
        for segment in segments:
            if re.search(r'\b(Institute|University|Academy|College)\b', segment, re.IGNORECASE):
                found = segment
                break
        if not found:
            found = part
        institutions.append(found)
    return list(set(institutions)) if institutions else None

def extract_institutions_scopus(affiliation):
    """
    Extract institutions from Scopus-style affiliation strings.
    These typically contain an author name, the institution,
    and additional details such as email. We:
      - Split on semicolons,
      - Filter out segments with email info or that are too short,
      - Then return segments that contain typical institution keywords.
    If nothing qualifies, we fall back on the second segment.
    """
    if not isinstance(affiliation, str):
        return None
    parts = [p.strip() for p in affiliation.split(';') if p.strip()]
    filtered_parts = []
    for p in parts:
        if 'email:' in p.lower() or ('@' in p):
            continue
        if len(p.split()) < 3:
            continue
        filtered_parts.append(p)
    institutions = []
    for part in filtered_parts:
        if re.search(r'\b(Institute|University|School|Academy|College)\b', part, re.IGNORECASE):
            institutions.append(part)
    if not institutions and len(parts) > 1:
        institutions.append(parts[1])
    return list(set(institutions)) if institutions else None

def plot_institution_contribution(input_csv):
    """
    Reads a CSV file with columns: Affiliation, Countries, Year.
    Based on the input type (IEEE vs Scopus), extracts institution names
    and appends or simplifies them with their country. The function then groups
    the data, takes the top 10 institutions by contribution, and plots a bar chart.
    """
    df = pd.read_csv(input_csv)
    
    # Choose extraction based on the filename
    if "scopus" in input_csv.lower():
        extractor = extract_institutions_scopus
    else:
        extractor = extract_institutions_generic

    df['Institutions'] = df['Affiliation'].apply(extractor)
    
    # Explode the list so that each institution becomes its own row
    df_exploded = df.explode('Institutions').dropna(subset=['Institutions'])
    
    # Update the institution labels by appending or simplifying with the country.
    if "scopus" in input_csv.lower():
        df_exploded["Institutions"] = df_exploded.apply(
            lambda row: simplify_scopus_institution(row["Institutions"], parse_country_field(row["Countries"])), axis=1)
    else:
        df_exploded["Institutions"] = df_exploded.apply(
            lambda row: append_country_institution(row["Institutions"], parse_country_field(row["Countries"])), axis=1)
    
    # Group by institution and count contributions
    inst_counts = df_exploded.groupby('Institutions').size().reset_index(name="Count")
    inst_counts = inst_counts.sort_values("Count", ascending=False).head(10)
    
    # Plot the top 10 institutions
    plt.figure(figsize=(12, 6))
    sns.barplot(x="Count", y="Institutions", data=inst_counts, palette="viridis")
    plt.title("Top 10 Institution Contributions")
    plt.xlabel("Number of Contributions")
    plt.ylabel("Institution (with Country)")
    plt.tight_layout()
    plt.show()
if __name__ == "__main__":
    #run_all_affiliations()
    paths = ["IEEE",  "Scopus"]
    #plot_country_frequency(paths)
    #plot_country_evolution(paths)
    for i in paths:
        input_csv = f"affiliation_country_{i}.csv"
        plot_institution_contribution(input_csv)