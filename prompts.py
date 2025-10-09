DEFAULT_RESEARCH_PROMPT = """



Follow the below steps:
Research the typical materials, components, and construction details for this general product category. Include:
1) Common materials used in manufacturing (metals, fabrics, plastics, etc.)
2) Standard components that are always present but might not be explicitly mentioned (handles, coatings, fasteners, etc.)
3) Typical total product weight ranges for products in this category
4) Typical parts and percentages by volume in this category (must be volume and not weight); when estimating material volume, consider only parts and materials, not space or air.
5) Common manufacturing countries and material source countries
6) Standard construction methods and material densities
7) Any specialized components or materials specific to this product type
Provide this as comprehensive baseline knowledge that can be used to enhance analysis of specific products in this category.

DO NOT CREATE ANY TABLES. ONLY PROVIDE TEXT ANALYSIS.





"""
####################################################################################################################################################################################
#                DEFAULT URL PROMPT
#####################################################################################################################################################################################
DEFAULT_URL_PROMPT = """




**PRODUCT URL SEARCH AND ANALYSIS**

Based on the search results provided by SerpAPI, identify and extract information from actual product listings. The search results will contain URLs and snippets from various retailers.

**STEP 1: IDENTIFY PRODUCT URLS FROM SEARCH RESULTS**
From the SerpAPI search results provided, identify URLs that contain:
- Amazon product listings
- Manufacturer/brand official pages  
- Home Depot, Walmart, Lowes, or other major retailer listings
- Any other relevant product pages

**STEP 2: EXTRACT PRODUCT SPECIFICATIONS**
For each identified URL, extract the following information from the search snippet or description:
- Product weight (usually expressed in "lbs")
- Country of Origin (usually expressed as "Made in [country]" or "Country of Origin: [Country]"
- Dimensions (length, width, height)
- Capacity/volume
- Key features and specifications
- Price information
- Material descriptions
- Model numbers or UPC codes

**STEP 3: COMPILE URL FINDINGS**
Provide a structured summary of:

**VERIFIED PRODUCT URLS FOUND:**
- **Amazon URL:** [Extract Amazon URL from search results if present]
- **Manufacturer URL:** [Extract official brand URL from search results if present]  
- **Retailer URLs:** [Extract other retailer URLs from search results if present]

**EXTRACTED SPECIFICATIONS FROM SEARCH RESULTS:**
- Product weight: [From search snippets or description]
- Dimensions: [From search snippets or description]
- Capacity: [From search snippets or description]
- Key features: [From search snippets or description]
- Price range: [From search snippets or description]

**SEARCH RESULT ANALYSIS:**
- Total URLs found: [Count of relevant product URLs]
- Best sources identified: [List most authoritative sources found]
- Missing information: [Note what specs weren't found in search results]

**NOTE:** Work with the actual search results provided by SerpAPI. Do not generate or assume URLs - only use what is actually returned in the search results.







"""
####################################################################################################################################################################################
#                DEFAULT PRODUCT PROMPT
#####################################################################################################################################################################################
DEFAULT_PRODUCT_PROMPT = """



**MANDATORY FIRST STEP: Carefully review the GENERAL PRODUCT KNOWLEDGE provided above. Use it as your baseline for understanding typical materials, components, and construction for this product category.**
Now analyze THIS SPECIFIC PRODUCT ONLY, using the general knowledge as your foundation.
**YOU MUST PROVIDE ONLY TEXT ANALYSIS - NO TABLES**

Write out your complete step-by-step methodology:

Step 1: Extract from General Knowledge
- List ALL materials mentioned in the general product research
- Note typical volume percentages for each material in this category
- Include standard components (fasteners, threads, coatings, etc.)

Step 2: Analyze SerpAPI Search Results and Visit Product Pages
- Use the SerpAPI search results and URL analysis provided above
- **MANDATORY: Actually visit each product URL found in the SerpAPI results**
- **VERIFICATION REQUIRED: For each URL visited, state:**
  - "VISITED: [URL]"
  - "PAGE CONTENT FOUND: [Brief description of what was on the page]"
  - "SPECIFICATIONS EXTRACTED: [List actual specs found on that page]"
- Extract detailed product specifications from the actual web pages (not just snippets)
- Be sure to find a listing for product weight usually written as "weight" or where the result is expressed in "lbs" or "pounds"; do not use placeholder or assumed data as this must be listed on the sites
- Also be sure to find the manufacturing location which will be expressed as "made in [country]" or "manufactured in [country]" or "Country of origin"
- Cross-reference information from multiple retailer pages you actually visited
- Do not use placeholder or assumed data - only use information from pages you actually accessed

Step 3: Create Complete Material List
- Start with ALL materials from general knowledge
- Add any unique materials for this specific product found in Step 2 from actual web pages
- Cross-reference material information between different retailer pages you visited
- Adjust percentages based on specific product features found on actual product pages
- Ensure all percentages total exactly 100%

Step 4: For each material, determine the primary Manufacturing Process that would be required to transform the raw material into the product part for assembly.

Step 5: Technical Data and Source Verification
- Use actual product weight from web pages you visited
- Apply material densities from general knowledge
- Calculate weights using: (Actual Total Weight × Volume % × Density Ratio)
- **VERIFY ALL CALCULATIONS**: Show your math for weight distribution

**PERPLEXITY USERS: You MUST actually visit the URLs and confirm what you found on each page. Do not proceed without visiting the actual product pages.**



"""
####################################################################################################################################################################################
#                DEFAULT IMAGE PROMPT
#####################################################################################################################################################################################
DEFAULT_IMAGE_PROMPT = """

Based on the Product BOM analysis above and this image of the product, provide a detailed visual assessment that identifies:

1.  **MATERIAL CORRECTIONS**: Compare what you see in the image vs. the BOM analysis
    * Identify materials that appear different from the BOM estimates
    * Note any missing components visible in the image
    * Estimate corrected material percentages by volume based on visual evidence

2.  **STRUCTURAL ANALYSIS**: Analyze the construction details visible
    * Joint types, assembly methods, component thickness
    * Surface treatments, coatings, finishes
    * Any additional hardware or components not mentioned in BOM

3.  **QUALITY INDICATORS**: Visual cues about manufacturing
    * Build quality, material thickness, construction type
    * Any visible branding, labels, or country of origin marks

4.  **MATERIAL PROPERTIES RESEARCH**: For each material identified, research and provide:
    * Material density (lb/ft³)
    * **CRITICAL LOGIC:** Assume material source countries are geographically and economically close to the manufacturing Country of Origin ({country_of_origin}).
    * Typical source countries for this material type (following the logic above).
    * Standard CO2 emissions factors (kg CO2e/kg) for sourcing/processing
    * Manufacturing process CO2 emissions (kg CO2e/kg)
    * Transportation CO2 factor (kg CO2e/kg-km)
    * **DISTANCE CALCULATION:** Calculate a two-part journey. First, find the distance from the logical source country to **{country_of_origin}**. Second, find the distance from **{country_of_origin}** to the **USA**. Provide the SUM of these two distances.

5.  **VOLUME PERCENTAGE ESTIMATION**: Based on visual analysis, estimate the volume percentage each material represents of the total product

**REQUIRED JSON OUTPUT WITH RESEARCHED DATA:**
```json
{{
  "total_weight_lbs": [Total Weight from previous analysis],
  "materials": [
    {{
      "name": "[Material Name]",
      "volume_percentage": [Volume percentage of total product, must sum to 100],
      "density_lb_ft3": [Researched density value],
      "source_country": "[Primary source country - research typical sources]",
      "co2_sourcing_kg_per_kg": [Researched CO2 factor for material sourcing/processing],
      "co2_manufacturing_kg_per_kg": [Researched CO2 factor for manufacturing process],
      "transport_method": "[Research typical method e.g., Ocean Freight, Air Freight, Rail]",
      "distance_km": [SUM of distance from source country to {country_of_origin} AND distance from {country_of_origin} to USA],
      "manufacturing_process": "[Research primary manufacturing process for this material]"
    }}
  ],
  "total_volume_percentage": [Sum of all volume percentages - must equal 100],
  "confidence_level": "[High/Medium/Low] - based on visual clarity and research quality"
}}




"""
####################################################################################################################################################################################
#                DEFAULT RECONCILIATION PROMPT
#####################################################################################################################################################################################
DEFAULT_RECONCILIATION_PROMPT = """















Create a comprehensive professional assessment following this EXACT format and structure:

**Trace Logic AI Environmental Product Assessment**

**Overview**
- UPC: [Extract from product research or estimate based on product type]
- Product Name: [Exact product name]
- Manufacturer: [Brand name]
- Carbon Footprint*: [Use calculated total from math step] kg CO2e
- Assessment Date: [Current date]

**General Product Attributes**
- Weight: [Use product weight from earlier steps] lbs
- Country of Origin: [Manufacturing country from research]

**Bill of Materials (BOM) and Material/Energy Flows**
Create a table using the CALCULATED MATHEMATICAL DATA provided. Only include parts and materials, not space or air. Use these EXACT columns (use | delimiters):

Part | Material | Material Source Country | Volume Percentage (%) | Published Material Density (lb/ft^3) | Material Volume Density | Volume Density Percentage (%) | Product Weight (lbs) | Material Part Weight (Lbs) | Material Part Weight (Kg) | Published Sourcing and Processing Carbon Footprint (Kg CO2e/Kg weight) | Sourcing and Processing Carbon Footprint Reference | Material Part Sourcing and Processing Carbon Footprint (Kg CO2e) | Material Mfg Process | Mfg Process Published Carbon Footprint (Kg CO2e/Kg weight) | Mfg Process Carbon Footprint Reference | Material Part Mfg Process Carbon Footprint (Kg CO2e) | Material Journey Method | Material Journey Distance (Km, Material Source Country-to-Country of Origin-to-USA) | Transport Published Carbon Footprint (Kg CO2e/Kg-Km) | Transport. Carbon Footprint Reference | Material Part Journey Carbon Footprint (Kg CO2e) | Material End of Life | Published End of Life Carbon Footprint (Kg CO2e/Kg weight) | End of Life Carbon Footprint Reference | Material End of LIfe Carbon Footprint (Kg CO2e)

**CRITICAL TABLE REQUIREMENTS:**
- Use the pre-calculated mathematical data from the calculation step
- Include ALL materials from calculated analysis; make sure that the materials column shows ONLY the physical material, e.g. stainless steel, Polyurethane foam
- All weights, densities, and CO2 values are already computed - use them directly
- Include numbered references [1], [2], [3], etc. for all footprint values
- DO NOT recalculate - use the provided calculated values
- Show volume percentages AND density-based weight calculations
- Material weights are calculated using density distribution, not simple volume percentages
- Use "Ocean Shipping" or "Rail Transport" for Material Journey Method
- Use the total product weight from earlier steps for the Product Weight column

***System Boundary**
Cradle-to-Gate assessment includes all materials sourced and processed, transported to manufacturing facility, manufactured and assembled, and transported to nearest port in USA. End of life landfill emissions are also included.

**Product URL Match:**
[List 3-4 verified URLs from the product research]

**Summary of Assessment**

## Methodology/Approach
[Detailed 2-3 paragraph explanation of the research approach including density-based mathematical calculation step; include this sentence at the end of this paragraph: "Individual material weights were calculated using volumetric assessment and converted to kilograms using published material densities."]

## General Category Research
[2-3 paragraphs covering standard materials, manufacturing geography, and typical processes for this product category]

## Product-Specific Adjustments
[2-3 paragraphs explaining how specific product features influenced the analysis]

## Image-Related Adjustments
[2-3 paragraphs describing how visual analysis provided material property research and volume percentage estimations]

## Key Assumptions
[3-4 paragraphs covering geographic sourcing, technical specifications, material processing, volume estimations, density-based calculations, etc.]

## Carbon Footprint Methodology
[2-3 paragraphs explaining the calculated methodology and total footprint breakdown from the math step.]

**SOURCING REFERENCES:**
Use these standard reference sources and include them at the bottom:
[1] PlasticsEurope LCA Database: polymer production emission factors
[2] WorldSteel LCA Eco-profiles: steel production emissions factors  
[3] EPA Manufacturing Database: US manufacturing energy data
[4] IMO GHG Studies: shipping emission factors
[5] NREL Transportation Database: transport emission factors
[6] EPA GHG Emission Factor Hub: end of life treatment of sold products.

IMPORTANT: Use the pre-calculated density-based mathematical data throughout this assessment. The system has computed all weights using volume percentages multiplied by material densities to create a more accurate weight distribution than volume alone. Material weights are calculated from each material's percentage of total volume-density. For the Product Weight column, use the same total product weight value for all rows.







"""
