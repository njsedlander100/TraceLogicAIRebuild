from flask import Flask, render_template_string, request, jsonify
import os
import requests
import base64
import json
import re
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
from datetime import datetime

# API Keys
PPLX_API_KEY = os.environ.get('PPLX_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY', '')  # New: SerpAPI key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

RESEARCH_TEMPLATE_DIR = 'research_templates'

####################################################################################################################################################################################
#                DEFAULT RESEARCH PROMPT
#####################################################################################################################################################################################
# Default prompts
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

DO NOT CREATE ANY TABLES. ONLY PROVIDE TEXT ANALYSIS..





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
- Product weight
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
- Product weight: [From search snippets]
- Dimensions: [From search snippets]
- Capacity: [From search snippets]
- Key features: [From search snippets]
- Price range: [From search snippets]

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

**System Boundary**
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
####################################################################################################################################################################################
#                HTML CODE
#####################################################################################################################################################################################


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TraceLogic.AI</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.23/jspdf.plugin.autotable.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="header">
                <h1>TraceLogic.AI</h1>
            </div>
            
            <div class="form-group">
                <label for="product-input">Product Name 👇</label>
                <input type="text" id="product-input" value="Coleman 120-Quart Cooler">
            </div>
            
            <div class="form-group">
                <label for="country-of-origin-input">Country of Origin (Optional) 👇</label>
                <input type="text" id="country-of-origin-input" placeholder="e.g., China, USA (Overrides research if filled)">
            </div>
            <div class="expander">
                <div class="expander-header" onclick="toggleExpander('research')">Category Research 👇</div>
                <div class="expander-content" id="research-content">
                    <div class="form-group">
                        <label>Input Method:</label>
                        <select id="research-method-select" onchange="toggleResearchMethod()">
                            <option value="prompt">Use Prompt</option>
                            <option value="manual">Use Manual Text</option>
                            {% if research_templates %}
                                <optgroup label="Load from Template">
                                    {% for template in research_templates %}
                                        <option value="{{ template }}">{{ template }}</option>
                                    {% endfor %}
                                </optgroup>
                            {% endif %}
                        </select>
                    </div>

                    <div id="research-prompt-section">
                        <textarea id="research-prompt" rows="8">{{ research_prompt }}</textarea>
                        <div class="llm-selection" style="margin-top: 15px;">
                            <h4>🤖 Select LLM</h4>
                            <div class="form-group">
                                <select id="llm-select">
                                    <option value="claude">Claude Sonnet</option>
                                    <option value="perplexity">Perplexity</option>
                                    <option value="openai">OpenAI GPT-4</option>
                                    <option value="gemini">Google Gemini</option>
                                </select>
                                <div class="llm-note">
                                    Note: Research steps always use web-capable models (Perplexity/Claude) for product lookup
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="research-manual-section" style="display: none;">
                        <textarea id="research-manual-text" rows="12" placeholder="Enter the complete 'General Category Research' text here. This will be used as the direct input for Step 1, skipping the API call."></textarea>
                    </div>
                </div>
            </div>

            <div class="expander">
                <div class="expander-header" onclick="toggleExpander('url-search')">🔗 URL Search  👇</div>
                <div class="expander-content" id="url-search-content">
                    <div class="form-group">
                        <label>Search Method:</label>
                        <select id="url-search-method-select" onchange="toggleUrlSearchMethod()">
                            <option value="api">API Search</option>
                            <option value="manual" selected>Manual URL Input</option>
                        </select>
                    </div>
            
                    <!-- API Search Section -->
                    <div id="api-search-section" style="display: none;">
                        <div class="form-group">
                            <label>Search Model:</label>
                            <select id="url-search-llm-select">
                                <option value="serpapi">SerpAPI Google Search</option>
                                <option value="perplexity">Perplexity</option>
                                <option value="claude">Claude Sonnet</option>
                                <option value="openai">OpenAI GPT-4</option>
                                <option value="gemini">Google Gemini</option>
                            </select>
                        </div>
                        <button class="btn" onclick="testURLSearch()" style="margin-bottom: 15px;">🔍 Test URL Search Only</button>
                        
                        <div class="form-group" style="margin-top: 15px;">
                            <label>📝 URL Search Prompt:</label>
                            <textarea id="url-prompt" rows="15">{{ url_prompt }}</textarea>
                        </div>
                    </div>
            
                    <!-- Manual URL Input Section -->
                    <div id="manual-url-section" style="display: block;">
                        <div style="display: flex; flex-direction: column; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 14px; font-weight: bold; color: #666;">Product URL 1 (Amazon/Primary Retailer):</label>
                                <input type="text" id="manual-url-1" class="url-input" placeholder="https://amazon.com/product-link..." style="width: 100%; padding: 8px; margin-top: 5px;">
                            </div>
                            <div>
                                <label style="font-size: 14px; font-weight: bold; color: #666;">Product URL 2 (Manufacturer/Brand Site):</label>
                                <input type="text" id="manual-url-2" class="url-input" placeholder="https://brandname.com/product-page..." style="width: 100%; padding: 8px; margin-top: 5px;">
                            </div>
                            <div>
                                <label style="font-size: 14px; font-weight: bold; color: #666;">Product URL 3 (Other Retailer):</label>
                                <input type="text" id="manual-url-3" class="url-input" placeholder="https://retailer.com/product-link..." style="width: 100%; padding: 8px; margin-top: 5px;">
                            </div>
                        </div>
                        <button class="btn" onclick="testManualURLs()" style="margin-top: 15px;">🔗 Test Manual URLs</button>
                        
                        <div class="form-group" style="margin-top: 15px;">
                            <label>📝 Manual URL Analysis Prompt:</label>
                            <textarea id="manual-url-prompt" rows="8" placeholder="Analyze the manually provided URLs and extract product specifications...">Based on the manually provided URLs below, extract detailed product specifications including weight, dimensions, materials, and features from each URL.</textarea>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Product Listing Analysis (formerly Product & BOM) -->
            <div class="expander">
                <div class="expander-header" onclick="toggleExpander('product')">Product Listing Analysis 👇</div>
                <div class="expander-content" id="product-content">
                    <textarea id="product-prompt" rows="15">{{ product_prompt }}</textarea>
                    <div class="form-group" style="margin-top: 15px;">
                        <label>Research Model:</label>
                        <select id="research-llm-select">
                            <option value="perplexity">Perplexity (Best for URLs)</option>
                            <option value="claude">Claude Sonnet</option>
                            <option value="openai">OpenAI GPT-4</option>
                            <option value="gemini">Google Gemini</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="expander">
                <div class="expander-header" onclick="toggleExpander('image-analysis')">📷 Multi-Image Product Analysis 👇</div>
                <div class="expander-content" id="image-analysis-content">
                    <div class="image-options">
                        <div class="image-option">
                            <input type="radio" id="auto-search" name="image-source" value="auto-search">
                            <label for="auto-search">🔍 Auto-Select Images</label>
                        </div>
                        <div class="image-option">
                            <input type="radio" id="manual-url" name="image-source" value="manual-url" checked>
                            <label for="manual-url">🔗 Enter Image URLs</label>
                        </div>
                    </div>
                    
                    <div id="auto-search-group" class="image-input-group">
                        <button class="btn-search-images" onclick="searchProductImages()">🔍 Find & Auto-Select First 3 Images</button>
                        <div id="auto-search-results" class="auto-search-results"></div>
                    </div>
                    
                    <div id="manual-url-group" class="image-input-group active">
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            <div>
                                <label style="font-size: 12px; font-weight: bold; color: #666;">Image 1 (Main/Front View):</label>
                                <input type="text" id="image-url-1" class="url-input" placeholder="Paste first image URL here...">
                            </div>
                            <div>
                                <label style="font-size: 12px; font-weight: bold; color: #666;">Image 2 (Side/Interior View):</label>
                                <input type="text" id="image-url-2" class="url-input" placeholder="Paste second image URL here...">
                            </div>
                            <div>
                                <label style="font-size: 12px; font-weight: bold; color: #666;">Image 3 (Detail/Hardware View):</label>
                                <input type="text" id="image-url-3" class="url-input" placeholder="Paste third image URL here...">
                            </div>
                        </div>
                        <button class="btn-search-images" onclick="previewManualImages()">Preview All Images</button>
                    </div>
                    
                    <div id="selected-image-preview" class="selected-image-preview"></div>
                    
                    <div class="form-group" style="margin-top: 15px;">
                        <label>Vision Model:</label>
                        <select id="vision-llm-select">
                            <option value="claude">Claude 3 Vision</option>
                            <option value="openai">OpenAI GPT-4V (Best for Multi-Image)</option>
                            <option value="perplexity">Perplexity (Fallback)</option>
                            <option value="gemini">Google Gemini (Text only)</option>
                        </select>
                    </div>
                    <button class="btn" onclick="testImageAnalysis()" style="margin-bottom: 15px;">📷 Test Image Analysis Only</button>
                    
                    <div class="expander" style="margin-top: 15px;">
                        <div class="expander-header" onclick="toggleExpander('image')">Multi-Image Analysis Prompt 👇</div>
                        <div class="expander-content" id="image-content">
                            <textarea id="image-prompt" rows="12">{{ image_prompt }}</textarea>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Final Product Assessment (formerly Final BOM Table) -->
            <div class="expander">
                <div class="expander-header" onclick="toggleExpander('reconciliation')">Final Product Assessment 👇</div>
                <div class="expander-content" id="reconciliation-content">
                    <textarea id="reconciliation-prompt" rows="12">{{ reconciliation_prompt }}</textarea>
                </div>
            </div>
            
            <button class="btn" onclick="runCompleteAnalysis()">🍃 Run Complete Analysis</button>
        </div>
        
        <div class="main-content">
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div id="loading-text">Processing...</div>
            </div>
            
            <div id="results-container">
                <div class="header">
                    <h2>Analysis Results</h2>
                    <p>Run an analysis to see results here</p>
                </div>
            </div>
        </div>
    </div>





    <script>
        let analysisState = {
            generalResearch: null,
            productBOM: null,
            imageAnalysis: null,
            finalBOM: null,
            selectedImageUrl: null
        };
        
        document.addEventListener('DOMContentLoaded', function() {
            // Set default image URLs
            const defaultImageUrls = [
                'https://dks.scene7.com/is/image/GolfGalaxy/20COLU120QTHRDCLRREC_Twilight?qlt=70&wid=1100&fmt=pjpeg&op_sharpen=1',
                'https://photos-us.bazaarvoice.com/photo/2/cGhvdG86Y29sZW1hbi11cw/fc44c487-975f-519a-ae67-4ee7deb71ba1',
                'https://photos-us.bazaarvoice.com/photo/2/cGhvdG86Y29sZW1hbi11cw/6b110e50-d137-5833-9fe5-6bce6ca14890'
            ];

            // ADD THESE LINES FOR DEFAULT MANUAL URLS:
            const defaultManualUrls = [
                'https://www.coleman.com/coolers-drinkware/coolers/hard-coolers/classic-120-quart-hard-cooler/SP_271358.html',
                'https://www.dickssportinggoods.com/p/coleman-120-quart-hard-ice-chest-cooler-20colu120qthrdclrrec/20colu120qthrdclrrec?recid=oosproduct_PageElement_oosproduct_rr_2_42843_&rrec=true',
                'https://www.amazon.com/dp/B0BDGF2RHF?ref_=cm_sw_r_cp_ud_dp_3F1Q63Q8G9FEQ6J74XEG'
            ];
            
            document.getElementById('manual-url-1').value = defaultManualUrls[0];
            document.getElementById('manual-url-2').value = defaultManualUrls[1];
            document.getElementById('manual-url-3').value = defaultManualUrls[2];
            
            document.getElementById('image-url-1').value = defaultImageUrls[0];
            document.getElementById('image-url-2').value = defaultImageUrls[1];
            document.getElementById('image-url-3').value = defaultImageUrls[2];
            
            analysisState.selectedImageUrls = defaultImageUrls;
            showImagePreview();
            
            const imageSourceInputs = document.querySelectorAll('input[name="image-source"]');
            imageSourceInputs.forEach(input => {
                input.addEventListener('change', function() {
                    document.querySelectorAll('.image-input-group').forEach(group => {
                        group.classList.remove('active');
                    });
                    document.getElementById(this.value + '-group').classList.add('active');
                    
                    // HANDLE PREVIEW BASED ON MODE
                    if (this.value === 'auto-search') {
                        // HIDE PREVIEW IN AUTO-SELECT MODE
                        document.getElementById('selected-image-preview').innerHTML = '';
                    } else if (this.value === 'manual-url') {
                        // SHOW PREVIEW IN MANUAL MODE
                        showImagePreview();
                    }
                });
            });
        });
        
        // ADD THESE NEW SIMPLE FUNCTIONS
        function showImagePreview() {
            const previewContainer = document.getElementById('selected-image-preview');
            if (!previewContainer) return;
            
            // DON'T SHOW ANYTHING IN AUTO-SELECT MODE
            const autoMode = document.getElementById('auto-search').checked;
            if (autoMode) {
                previewContainer.innerHTML = '';
                return;
            }
            
            // Only show for manual mode
            const manualUrls = [
                document.getElementById('image-url-1').value.trim(),
                document.getElementById('image-url-2').value.trim(),
                document.getElementById('image-url-3').value.trim()
            ].filter(url => url);
            
            if (manualUrls.length === 0) {
                previewContainer.innerHTML = '';
                return;
            }
            
            analysisState.selectedImageUrls = manualUrls;
            
            const gridHtml = manualUrls.map((url, index) => {
                const labels = ['Main/Front View', 'Side/Interior View', 'Detail/Hardware View'];
                return `
                    <div class="selected-image-item">
                        <img src="${url}" alt="${labels[index] || `Image ${index + 1}`}" style="max-width: 100%; max-height: 120px;">
                        <div class="image-label">${labels[index] || `Image ${index + 1}`}</div>
                    </div>
                `;
            }).join('');
            
            previewContainer.innerHTML = `
                <div><strong>Selected Images (${manualUrls.length}/3):</strong></div>
                <div class="selected-images-grid">${gridHtml}</div>
            `;
        }

        function toggleResearchMethod() {
            const selectedValue = document.getElementById('research-method-select').value;
            const promptSection = document.getElementById('research-prompt-section');
            const manualSection = document.getElementById('research-manual-section');

            // Hide all sections first
            promptSection.style.display = 'none';
            manualSection.style.display = 'none';

            if (selectedValue === 'prompt') {
                promptSection.style.display = 'block';
            } else if (selectedValue === 'manual') {
                manualSection.style.display = 'block';
            }
            // If a template file is selected, no section needs to be visible
        }
        
        function previewManualImages() {
            const urls = [
                document.getElementById('image-url-1').value.trim(),
                document.getElementById('image-url-2').value.trim(),
                document.getElementById('image-url-3').value.trim()
            ].filter(url => url);
            
            if (urls.length === 0) {
                alert('Please enter at least one image URL');
                return;
            }
            
            analysisState.selectedImageUrls = urls;
            showImagePreview();
        }
        
        function displayImageOptions(images) {
            const resultsContainer = document.getElementById('auto-search-results');
            if (!images || images.length === 0) {
                resultsContainer.innerHTML = '<div style="color: #666;">No images found.</div>';
                return;
            }
            
            // Create the image grid with first 3 pre-selected
            resultsContainer.innerHTML = images.map((img, index) => {
                // HIGHLIGHT FIRST 3 IMAGES WITH GREEN BORDER
                const isSelected = index < 3;
                const borderStyle = isSelected ? 'border: 3px solid #28a745 !important; background: #d4edda !important;' : 'border: 2px solid #ddd;';
                return `
                    <div class="image-option-card" data-index="${index}" onclick="toggleImageSelect(${index})" style="${borderStyle}">
                        <img src="${img.thumbnail || img.url}" alt="Image ${index + 1}" style="width: 100%; height: 80px; object-fit: cover;">
                        <div class="image-title">${(img.title || `Option ${index + 1}`).substring(0, 30)}...</div>
                    </div>
                `;
            }).join('');
            
            // Store images and auto-select first 3
            window.searchedImages = images;
            analysisState.selectedImageUrls = images.slice(0, 3).map(img => img.url);
        }
        
        // ADD this new function for toggling selections:
        function toggleImageSelect(index) {
            if (!window.searchedImages) return;
            
            const image = window.searchedImages[index];
            const card = document.querySelector(`[data-index="${index}"]`);
            
            if (analysisState.selectedImageUrls.includes(image.url)) {
                // Remove from selection
                analysisState.selectedImageUrls = analysisState.selectedImageUrls.filter(url => url !== image.url);
                card.style.border = '2px solid #ddd';
                card.style.background = '';
            } else if (analysisState.selectedImageUrls.length < 3) {
                // Add to selection
                analysisState.selectedImageUrls.push(image.url);
                card.style.border = '3px solid #007bff';
                card.style.background = '#e3f2fd';
            } else {
                alert('Maximum 3 images can be selected. Please deselect one first.');
                return;
            }
            
            showImagePreview();
            console.log('Current selection:', analysisState.selectedImageUrls);
        }
        
        
        // Search for product images using SerpAPI
        async function searchProductImages() {
            const productName = document.getElementById('product-input').value;
            const resultsContainer = document.getElementById('auto-search-results');
            
            resultsContainer.innerHTML = '<div class="loading-images">🔍 Searching for product images...</div>';
            
            try {
                const response = await fetch('/api/search-images', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product: productName })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    resultsContainer.innerHTML = `<div style="color: red;">Error: ${data.error}</div>`;
                    return;
                }
                
                displayImageOptions(data.images);
                
            } catch (error) {
                resultsContainer.innerHTML = `<div style="color: red;">Failed to search images: ${error.message}</div>`;
            }
        }
        
        
        function toggleExpander(id) {
            const content = document.getElementById(id + '-content');
            content.classList.toggle('active');
        }
        
        function showLoading(text) {
            document.getElementById('loading').classList.add('active');
            document.getElementById('loading-text').textContent = text;
        }
        
        function hideLoading() {
            document.getElementById('loading').classList.remove('active');
        }
        
        function addResult(title, content, emoji = '') {
            const container = document.getElementById('results-container');
            const result = document.createElement('div');
            result.className = 'result';
            
            // Check if this should be collapsible (Step 1, Step 2a, Step 2b, and Step 3)
            const isCollapsible = title.includes('Step 1:') || title.includes('Step 2a:') || title.includes('Step 2b:') || title.includes('Step 3:') || title.includes('Step 3.5:');
            
            // Try to convert CSV-like content to table ONLY for Step 4 (Final Product Assessment)
            const isStep4 = title.includes('Step 4:');
            
            if (isCollapsible) {
                // Create collapsible section for Step 1, Step 2a, Step 2b, and Step 3
                const collapseId = 'collapse-' + Math.random().toString(36).substr(2, 9);
                const isStep1 = title.includes('Step 1:');
                const defaultDisplay = isStep1 ? 'none' : 'none'; // All start collapsed
                const defaultIcon = isStep1 ? '▶️' : '▶️';
                
                result.innerHTML = `
                    <h3 onclick="toggleCollapse('${collapseId}')" style="cursor: pointer; user-select: none;">
                        ${emoji} ${title} 
                        <span id="icon-${collapseId}" style="float: right;">${defaultIcon}</span>
                    </h3>
                    <div id="${collapseId}" style="display: ${defaultDisplay}; margin-top: 10px;">
                        <pre>${content}</pre>
                    </div>
                `;
            } else if (isStep4) {
                // For Step 4, separate table from methodology text
                const { tableHTML, methodologyText } = separateTableAndText(content);

                // **CRITICAL**: This line stores the raw content in a hidden div for the PDF export
                const rawContentHTML = `<div class="raw-step4-content" style="display:none;">${content.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>`;

                result.innerHTML = `
                    <h3>${emoji} ${title}</h3>
                    ${rawContentHTML} 
                    ${tableHTML ? `<div class="table-container">${tableHTML}</div>` : ''}
                    ${methodologyText ? `<pre>${methodologyText}</pre>` : `<pre>${content}</pre>`}
                `;
            } else {
                // Regular result for other steps - text only
                result.innerHTML = `
                    <h3>${emoji} ${title}</h3>
                    <pre>${content}</pre>
                `;
            }
            
            container.appendChild(result);
        }
        
        function separateTableAndText(content) {
            const lines = content.split('\\n');
            let tableLines = [];
            let textLines = [];
            let inTable = false;
            
            for (let line of lines) {
                const pipeCount = (line.match(/\\|/g) || []).length;
                
                // If this line has lots of pipes, it's part of the table
                if (pipeCount >= 10) {
                    tableLines.push(line);
                    inTable = true;
                } else if (inTable && pipeCount >= 3) {
                    // Continue table if we're in table mode and still have some pipes
                    tableLines.push(line);
                } else if (inTable && line.trim().match(/^[\\-\\+\\|\\s]+$/)) {
                    // Skip separator lines in table
                    continue;
                } else {
                    // This is text content
                    inTable = false;
                    textLines.push(line);
                }
            }
            
            const tableHTML = tableLines.length > 0 ? tryConvertToTable(tableLines.join('\\n')) : null;
            const methodologyText = textLines.join('\\n').trim();
            
            return { tableHTML, methodologyText };
        }
        
        function toggleCollapse(id) {
            const content = document.getElementById(id);
            const icon = document.getElementById('icon-' + id);
            
            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.textContent = '🔽';
            } else {
                content.style.display = 'none';
                icon.textContent = '▶️';
            }
        }
        
        // Updated tryConvertToTable function with comprehensive CO2 calculation
        function tryConvertToTable(content) {
            // ONLY convert actual structured data tables with LOTS of delimiters
            const lines = content.split('\\n').filter(line => line.trim());
            
            // Look for lines with MANY pipes (actual BOM tables)
            const pipeLines = lines.filter(line => {
                const pipeCount = (line.match(/\\|/g) || []).length;
                return pipeCount >= 10; // Must have 10+ pipes for real table
            });
            
            // Look for lines with MANY commas (actual CSV data)
            const csvLines = lines.filter(line => {
                const commaCount = (line.match(/,/g) || []).length;
                return commaCount >= 8; // Must have 8+ commas for real table
            });
            
            let delimiter = '';
            let dataLines = [];
            
            if (pipeLines.length >= 2) {
                delimiter = '|';
                dataLines = pipeLines;
            } else if (csvLines.length >= 2) {
                delimiter = ',';
                dataLines = csvLines;
            } else {
                return null; // Not a real data table
            }
            
            // Parse the table - keep original logic but improve alignment
            const rows = dataLines.map(line => {
                return line.split(delimiter).map(cell => cell.trim()).filter(cell => cell.length > 0);
            });
            
            if (rows.length < 2 || rows[0].length < 5) return null; // Need header + data + multiple columns
            
            const headers = rows[0];
            const dataRows = rows.slice(1);
            
            // Calculate totals for numeric columns with enhanced CO2 tracking
            const totals = {};
            let totalSourcingCO2 = 0;
            let totalManufacturingCO2 = 0;
            let totalTransportationCO2 = 0;
            let totalEndOfLifeCO2 = 0;
            
            headers.forEach((header, index) => {
                let sum = 0;
                let hasNumbers = false;
                
                dataRows.forEach(row => {
                    const cellValue = row[index] || '';
                    const numericValue = parseFloat(cellValue.replace(/[^\\d.-]/g, ''));
                    
                    if (!isNaN(numericValue) && isFinite(numericValue)) {
                        sum += numericValue;
                        hasNumbers = true;
                        
                        // Enhanced CO2 tracking by column type - USE EXACT COLUMN NAMES
                        if (header === 'Material Part Sourcing and Processing Carbon Footprint (Kg CO2e)') {
                            totalSourcingCO2 += numericValue;
                        } else if (header === 'Material Part Mfg Process Carbon Footprint (Kg CO2e)') {
                            totalManufacturingCO2 += numericValue;
                        } else if (header === 'Material Part Journey Carbon Footprint (Kg CO2e)') {
                            totalTransportationCO2 += numericValue;
                        } else if (header === 'Material End of LIfe Carbon Footprint (Kg CO2e)'){
                            totalEndOfLifeCO2 += numericValue;
                        }
                    }
                });
                
                // ONLY calculate totals for these specific columns
                const shouldTotal = header.includes('Material Part Weight (Lbs)') ||
                                   header.includes('Material Part Weight (Kg)') ||
                                   header.includes('Volume Percentage') ||
                                   header.includes('Material Part Sourcing and Processing Carbon Footprint') ||
                                   header.includes('Material Part Mfg Process Carbon Footprint') ||
                                   header.includes('Material Part Journey Carbon Footprint') ||
                                   header.includes('Material End of LIfe Carbon Footprint'); // Added EoL
                
                totals[header] = (shouldTotal && hasNumbers) ? sum.toFixed(4) : '';
            });
            
            // Calculate comprehensive total CO2
            const comprehensiveTotalCO2 = totalSourcingCO2 + totalManufacturingCO2 + totalTransportationCO2 + totalEndOfLifeCO2;
            
            // Generate unique table ID for export
            const tableId = 'bom-table-' + Math.random().toString(36).substr(2, 9);
            
            // Generate HTML table with export button and better styling
            let tableHTML = `
                <div class="table-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4>📊 Bill of Materials</h4>
                    <div>
                        <button class="export-button" onclick="exportTableCSV('${tableId}')" style="padding: 5px 10px; cursor: pointer; margin-right: 5px;">📥 Export CSV</button>
                        <button class="export-button" onclick="exportPageHTML()" style="padding: 5px 10px; cursor: pointer; margin-right: 5px;">📄 Export HTML</button>
                        <button class="export-button" onclick="exportPDF('${tableId}')" style="padding: 5px 10px; cursor: pointer;">📑 Export PDF</button>
                    </div>
                </div>
                <table id="${tableId}" class="data-table" style="width: 100%; border-collapse: collapse; table-layout: auto;">
            `;
            
            // Header
            tableHTML += '<thead><tr>';
            headers.forEach(header => {
                tableHTML += `<th style="border: 1px solid #ddd; padding: 8px; background: #f5f5f5; font-weight: bold; text-align: left; white-space: nowrap;">${header}</th>`;
            });
            tableHTML += '</tr></thead>';
            
            // Body
            tableHTML += '<tbody>';
            dataRows.forEach(row => {
                tableHTML += '<tr>';
                headers.forEach((header, index) => {
                    const cell = row[index] || '';
                    const isNumber = /^\\$?[\\d,]+\\.?\\d*%?$/.test(cell.trim());
                    const className = isNumber ? 'number' : '';
                    const textAlign = isNumber ? 'right' : 'left';
                    tableHTML += `<td class="${className}" style="border: 1px solid #ddd; padding: 8px; text-align: ${textAlign};">${cell}</td>`;
                });
                tableHTML += '</tr>';
            });
            
            // Add totals row - ONLY show totals for specific columns
            tableHTML += '<tr style="background: #f0f8ff;">';
            headers.forEach((header, index) => {
                if (index === 0) {
                    tableHTML += '<td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">TOTALS</td>';
                } else {
                    const total = totals[header]; // This will be empty string for non-totaled columns
                    const textAlign = total ? 'right' : 'left';
                    tableHTML += `<td style="border: 1px solid #ddd; padding: 8px; text-align: ${textAlign}; font-weight: bold;">${total}</td>`;
                }
            });
            tableHTML += '</tr>';
            
            tableHTML += '</tbody></table>';
            
            // Enhanced CO2 summary with breakdown
            if (comprehensiveTotalCO2 > 0) {
                tableHTML += `
                    <div class="total-co2-highlight">
                        <h4>🌍 Total Carbon Footprint Breakdown</h4>
                        <div class="co2-breakdown">
                            ${totalSourcingCO2 > 0 ? `<div class="co2-item">📦 Sourcing & Processing: <strong>${totalSourcingCO2.toFixed(4)} kg CO₂</strong></div>` : ''}
                            ${totalManufacturingCO2 > 0 ? `<div class="co2-item">🏭 Manufacturing: <strong>${totalManufacturingCO2.toFixed(4)} kg CO₂</strong></div>` : ''}
                            ${totalTransportationCO2 > 0 ? `<div class="co2-item">🚛 Transportation: <strong>${totalTransportationCO2.toFixed(4)} kg CO₂</strong></div>` : ''}
                            ${totalEndOfLifeCO2 > 0 ? `<div class="co2-item">🗑️ End of Life: <strong>${totalEndOfLifeCO2.toFixed(4)} kg CO₂</strong></div>` : ''}
                        </div>
                        <div class="co2-total">
                            <strong>🎯 TOTAL PRODUCT CARBON FOOTPRINT: ${comprehensiveTotalCO2.toFixed(4)} kg CO₂</strong>
                        </div>
                    </div>
                `;
            }
            
            return tableHTML;
        }

        function exportPDF(tableId) {
            const { jsPDF } = window.jspdf;
            // Use jsPDF in landscape mode to give more room for the table
            const doc = new jsPDF({ orientation: 'landscape' });

            // --- 1. GATHER DATA FROM THE PAGE ---
            let headerText = '';
            let footerText = '';
            const step4Result = Array.from(document.querySelectorAll('.result h3')).find(h3 => h3.textContent.includes('Step 4: Final Product Assessment'))?.parentElement;

            if (step4Result) {
                // This now correctly finds the hidden div created by addResult
                const rawContentDiv = step4Result.querySelector('.raw-step4-content');
                if (!rawContentDiv) {
                    alert("Could not find the raw assessment text. The page structure might have changed.");
                    return;
                }
                const fullContent = rawContentDiv.textContent; 
                
                const bomTitle = 'Bill of Materials (BOM) and Material/Energy Flows';
                const systemBoundaryTitle = 'System Boundary';

                const headerEndIndex = fullContent.indexOf(bomTitle) + bomTitle.length;
                headerText = fullContent.substring(0, headerEndIndex).trim();
                
                const footerStartIndex = fullContent.indexOf(systemBoundaryTitle);
                if (footerStartIndex !== -1) {
                    footerText = fullContent.substring(footerStartIndex).trim();
                }
            } else {
                alert("Could not find the final assessment text.");
                return;
            }

            // --- 2. PROCESS TABLE DATA (This part remains the same) ---
            const table = document.getElementById(tableId);
            if (!table) { alert("BOM table not found."); return; }
            
            const head = [];
            const body = [];
            const foot = [];
            const columnsToHide = [3, 4, 5, 6, 7]; // Columns D-H

            const headerMap = {
                "Part": "Part", "Material": "Material", "Material Source Country": "Source",
                "Material Part Weight (Kg)": "Weight (Kg)", "Published Sourcing and Processing Carbon Footprint (Kg CO2e/Kg weight)": "Src CO2 Rate",
                "Sourcing and Processing Carbon Footprint Reference": "Src Ref", "Material Part Sourcing and Processing Carbon Footprint (Kg CO2e)": "Src CO2",
                "Material Mfg Process": "Mfg Process", "Mfg Process Published Carbon Footprint (Kg CO2e/Kg weight)": "Mfg CO2 Rate",
                "Mfg Process Carbon Footprint Reference": "Mfg Ref", "Material Part Mfg Process Carbon Footprint (Kg CO2e)": "Mfg CO2",
                "Material Journey Method": "Transport", "Material Journey Distance (Km, Material Source Country-to-Country of Origin-to-USA)": "Dist (Km)",
                "Transport. Published Carbon Footprint (Kg CO2e/Kg-Km)": "Trsp CO2 Rate", "Transport. Carbon Footprint Reference": "Trsp Ref",
                "Material Part Journey Carbon Footprint (Kg CO2e)": "Trsp CO2", "Material End of Life": "EoL",
                "Published End of Life Carbon Footprint (Kg CO2e/Kg weight)": "EoL Rate", "End of Life Carbon Footprint Reference": "EoL Ref",
                "Material End of LIfe Carbon Footprint (Kg CO2e)": "EoL CO2"
            };

            const headerCells = table.querySelectorAll('thead th');
            const filteredHeader = Array.from(headerCells)
                .filter((_, index) => !columnsToHide.includes(index))
                .map(th => headerMap[th.textContent.trim()] || th.textContent.trim());
            head.push(filteredHeader);

            const bodyRows = table.querySelectorAll('tbody tr');
            bodyRows.forEach(row => {
                const firstCellText = row.querySelector('td, th')?.textContent.trim();
                if (firstCellText.includes('---')) return;
                const rowData = Array.from(row.querySelectorAll('td'))
                                     .filter((_, index) => !columnsToHide.includes(index))
                                     .map(td => td.textContent.trim());
                if (firstCellText === 'TOTALS') {
                    foot.push(rowData);
                } else if (row.cells[1]?.textContent.trim() !== 'Interior Air Space') {
                    body.push(rowData);
                }
            });

            // --- 3. BUILD THE PDF ---
            doc.setFontSize(9);
            doc.text(headerText, 15, 20);

            const tableStartY = 65;
            doc.autoTable({
                head: head, body: body, foot: foot, startY: tableStartY, theme: 'grid',
                styles: { fontSize: 5, cellPadding: 1, halign: 'center' },
                headStyles: { fontStyle: 'bold', fillColor: [220, 220, 220], textColor: [0, 0, 0] },
                footStyles: { fontStyle: 'bold', fillColor: [240, 240, 240], textColor: [0, 0, 0] }
            });

            // **NEW LOGIC**: Handle multi-page text for the footer
            let finalY = doc.lastAutoTable.finalY + 10;
            doc.setFontSize(8);
            const pageHeight = doc.internal.pageSize.height;
            const margin = 15;
            // Split the long text block into lines that fit the page width
            const textLines = doc.splitTextToSize(footerText, doc.internal.pageSize.width - (margin * 2));
            
            textLines.forEach(line => {
                // If the next line will go off the page, add a new page
                if (finalY > pageHeight - margin) {
                    doc.addPage();
                    finalY = margin; // Reset Y position to the top margin
                }
                doc.text(line, margin, finalY);
                finalY += 4; // Move Y down for the next line
            });

            // --- 4. SAVE THE PDF ---
            const productName = document.getElementById('product-input').value.replace(/[^a-zA-Z0-9]/g, '_');
            doc.save(`TraceLogic_Assessment_${productName}.pdf`);
        }

        function exportPageHTML() {
            const pageHTML = document.documentElement.outerHTML;
            const blob = new Blob([pageHTML], { type: 'text/html;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            
            const productName = document.getElementById('product-input').value.replace(/[^a-zA-Z0-9]/g, '_');
            const filename = `TraceLogic_Archive_${productName}.html`;
            
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        // Simple CSV export function
        function exportTableCSV(tableId) {
            const table = document.getElementById(tableId);
            if (!table) {
                alert('Table not found');
                return;
            }
            
            const csvContent = [];
            
            // Add the full assessment text first
            const step4Results = document.querySelectorAll('[class="result"]');
            step4Results.forEach(result => {
                const title = result.querySelector('h3');
                if (title && title.textContent.includes('Step 4: Final Product Assessment')) {
                    const preElement = result.querySelector('pre');
                    if (preElement) {
                        // Add full assessment as one big cell
                        const assessmentText = preElement.textContent.replace(/"/g, '""');
                        csvContent.push(`"${assessmentText}"`);
                        csvContent.push(''); // Empty row for spacing
                        csvContent.push('"=== DETAILED BOM TABLE BELOW ==="');
                        csvContent.push(''); // Empty row for spacing
                    }
                }
            });
            
            // Then add the table data
            const rows = table.querySelectorAll('tr');
            rows.forEach(row => {
                const cols = row.querySelectorAll('td, th');
                const rowData = [];
                cols.forEach(col => {
                    let cellText = col.textContent.trim();
                    cellText = cellText.replace(/"/g, '""');
                    rowData.push(`"${cellText}"`);
                });
                csvContent.push(rowData.join(','));
            });
            
            const csvString = csvContent.join('\\n');
            const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            
            const productName = document.getElementById('product-input').value.replace(/[^a-zA-Z0-9]/g, '_');
            const filename = `TraceLogic_${productName}_Complete_Assessment.csv`;
            
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        function clearResults() {
            const container = document.getElementById('results-container');
            container.innerHTML = `
                <div class="header">
                    <h2>Analysis Results</h2>
                    <p>Analysis in progress...</p>
                </div>
            `;
        }
        
        function setComplete() {
            const container = document.getElementById('results-container');
            const header = container.querySelector('.header p');
            if (header) {
                header.textContent = 'Analysis Complete ✅';
            }
        }
        
        async function callAPI(endpoint, data) {
            // DON'T override LLM if already provided
            if (!data.llm) {
                const selectedLLM = document.getElementById('llm-select').value;
                data.llm = selectedLLM;
                console.log('No LLM provided, using default:', selectedLLM);
            } else {
                console.log('Using provided LLM:', data.llm);
            }
            
            console.log('Final request data:', data);
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`API call failed: ${response.statusText}`);
            }
            
            return await response.json();
        }

        async function testImageAnalysis() {
            // Check if images are selected
            if (!analysisState.selectedImageUrls || analysisState.selectedImageUrls.length === 0) {
                alert('Please select at least one image first!');
                return;
            }
            
            const visionLLM = document.getElementById('vision-llm-select').value;
            
            // Clear main results and show loading
            clearResults();
            showLoading(`📷 Testing Image Analysis with ${visionLLM.toUpperCase()}...`);
            
            try {
                const response = await callAPI('/api/multi-image-analysis', {
                    imageUrls: analysisState.selectedImageUrls,
                    productBOM: "Test image analysis without prior BOM data.",
                    prompt: document.getElementById('image-prompt').value,
                    visionLLM: visionLLM
                });
                
                hideLoading();
                addResult(`📷 Image Analysis Test Results (${visionLLM.toUpperCase()})`, response.result, '📷');
                
            } catch (error) {
                hideLoading();
                addResult('❌ Image Analysis Error', error.message, '❌');
            }
        }

        function toggleUrlSearchMethod() {
            const method = document.getElementById('url-search-method-select').value;
            const apiSection = document.getElementById('api-search-section');
            const manualSection = document.getElementById('manual-url-section');
            
            if (method === 'manual') {
                apiSection.style.display = 'none';
                manualSection.style.display = 'block';
            } else {
                apiSection.style.display = 'block';
                manualSection.style.display = 'none';
            }
        }
        
        async function testManualURLs() {
            const urls = [
                document.getElementById('manual-url-1').value.trim(),
                document.getElementById('manual-url-2').value.trim(),
                document.getElementById('manual-url-3').value.trim()
            ].filter(url => url);
            
            if (urls.length === 0) {
                alert('Please enter at least one URL');
                return;
            }
            
            const productName = document.getElementById('product-input').value;
            const prompt = document.getElementById('manual-url-prompt').value;
            
            clearResults();
            showLoading('🔗 Testing Manual URLs...');
            
            try {
                const response = await callAPI('/api/manual-url-test', {
                    product: productName,
                    urls: urls,
                    prompt: prompt
                });
                
                hideLoading();
                addResult('🔗 Manual URL Test Results', response.result, '🔗');
                
            } catch (error) {
                hideLoading();
                addResult('❌ Manual URL Error', error.message, '❌');
            }
        }


        async function testURLSearch() {
            const productName = document.getElementById('product-input').value;
            const searchLLM = document.getElementById('url-search-llm-select').value;
            
            // ADD DETAILED LOGGING
            console.log('=== URL SEARCH DEBUG ===');
            console.log('Product Name:', productName);
            console.log('Selected LLM from dropdown:', searchLLM);
            console.log('Dropdown element:', document.getElementById('url-search-llm-select'));
            console.log('All dropdown options:', Array.from(document.getElementById('url-search-llm-select').options).map(opt => opt.value));
            
            // Clear main results and show loading
            clearResults();
            showLoading(`🔍 Testing URL Search with ${searchLLM.toUpperCase()}...`);
            
            const urlSearchPrompt = `**URL SEARCH TEST FOR: ${productName}**
            
            ${document.getElementById('url-prompt').value}`;
        
            try {
                const requestData = {
                    product: productName,
                    prompt: urlSearchPrompt,
                    llm: searchLLM
                };
                
                console.log('Request data being sent:', requestData);
                
                const response = await callAPI('/api/url-search-test', requestData);
                
                console.log('Response received:', response);
                
                hideLoading();
                addResult(`🔗 URL Search Test Results (${searchLLM.toUpperCase()})`, response.result, '🔍');
                
            } catch (error) {
                console.error('URL Search Error:', error);
                hideLoading();
                addResult('❌ URL Search Error', error.message, '❌');
            }
        }
        
        async function runCompleteAnalysis() {
            clearResults();
            const productName = document.getElementById('product-input').value;
            
            try {
                // Step 1: Category Research (formerly General Research)
                const researchMethod = document.getElementById('research-method-select').value;
                
                if (researchMethod === 'manual') {
                    showLoading('📝 Step 1/6: Using manual category knowledge...');
                    const manualText = document.getElementById('research-manual-text').value;
                    if (!manualText.trim()) {
                        throw new Error('Manual text for Category Research is empty.');
                    }
                    analysisState.generalResearch = manualText;
                    addResult('Step 1: Category Research (Manual Input)', analysisState.generalResearch, '📝');
                } else if (researchMethod === 'prompt') {
                    showLoading('🔍 Step 1/6: Researching category knowledge...');
                    const researchData = await callAPI('/api/research', {
                        product: productName,
                        prompt: document.getElementById('research-prompt').value
                    });
                    analysisState.generalResearch = researchData.result;
                    addResult('Step 1: Category Research', analysisState.generalResearch, '🔍');
                } else {
                    // This means a template file was selected
                    showLoading(`📄 Step 1/6: Loading research template: ${researchMethod}...`);
                    const templateResponse = await fetch(`/api/get-research-template/${researchMethod}`);
                    if (!templateResponse.ok) {
                        throw new Error(`Failed to load template file: ${researchMethod}`);
                    }
                    const templateData = await templateResponse.json();
                    analysisState.generalResearch = templateData.content;
                    addResult(`Step 1: Category Research (from ${researchMethod})`, analysisState.generalResearch, '📄');
                }
                
                // Step 2a: URL Retrieval 
                showLoading('🔗 Step 2a/7: Retrieving product URLs...');
                const urlSearchMethod = document.getElementById('url-search-method-select').value;
                let urlResults;
                
                if (urlSearchMethod === 'manual') {
                    // Manual URL input
                    const manualUrls = [
                        document.getElementById('manual-url-1').value.trim(),
                        document.getElementById('manual-url-2').value.trim(),
                        document.getElementById('manual-url-3').value.trim()
                    ].filter(url => url);
                    
                    if (manualUrls.length === 0) {
                        throw new Error('Please enter at least one manual URL');
                    }
                    
                    const manualUrlPrompt = document.getElementById('manual-url-prompt').value;
                    
                    const manualUrlResponse = await fetch('/api/manual-url-test', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            product: productName,
                            urls: manualUrls,
                            prompt: manualUrlPrompt
                        })
                    });
                    
                    if (!manualUrlResponse.ok) {
                        throw new Error(`Manual URL processing failed: ${manualUrlResponse.statusText}`);
                    }
                    
                    const manualUrlData = await manualUrlResponse.json();
                    urlResults = manualUrlData.result;
                    addResult('Step 2a: Manual URL Input', urlResults, '🔗');
                    
                } else {
                    // API-based URL search
                    const urlSearchLLM = document.getElementById('url-search-llm-select').value;
                    const urlSearchPrompt = `**URL SEARCH FOR: ${productName}**
                    
                    ${document.getElementById('url-prompt').value}`;
                    
                    const urlResponse = await fetch('/api/url-search-test', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            product: productName,
                            prompt: urlSearchPrompt,
                            llm: urlSearchLLM
                        })
                    });
                    
                    if (!urlResponse.ok) {
                        throw new Error(`URL search failed: ${urlResponse.statusText}`);
                    }
                    
                    const urlData = await urlResponse.json();
                    urlResults = urlData.result;
                    addResult(`Step 2a: URL Retrieval (${urlSearchLLM.toUpperCase()})`, urlResults, '🔗');
                }
                
                // Step 2b: Product Listing Analysis
                showLoading('📋 Step 2b/7: Analyzing product listings...');
                const researchLLM = document.getElementById('research-llm-select').value;
                
                const productData = await callAPI('/api/product-bom', {
                    product: productName,
                    prompt: document.getElementById('product-prompt').value,
                    generalResearch: analysisState.generalResearch,
                    urlResults: urlResults, // Pass URL results as context
                    llm: researchLLM
                });
                
                analysisState.productBOM = productData.result;
                addResult(`Step 2b: Product Listing Analysis (${researchLLM.toUpperCase()})`, analysisState.productBOM, '📋');
                
                // Step 3: Product Image Analysis
                if (analysisState.selectedImageUrls && analysisState.selectedImageUrls.length > 0) {
                    showLoading('📷 Step 3/6: Analyzing multiple product images...');
                    const visionLLM = document.getElementById('vision-llm-select').value;
                    const countryOfOrigin = document.getElementById('country-of-origin-input').value.trim();
                    const imageData = await callAPI('/api/multi-image-analysis', {
                        imageUrls: analysisState.selectedImageUrls,
                        productBOM: analysisState.productBOM,
                        prompt: document.getElementById('image-prompt').value,
                        visionLLM: visionLLM,
                        countryOfOrigin: countryOfOrigin
                    });
                    analysisState.imageAnalysis = imageData.result;
                    addResult('Step 3: Multi-Image Product Analysis', analysisState.imageAnalysis, '📷');
                } else {
                    analysisState.imageAnalysis = 'No images provided - skipping visual analysis.';
                    addResult('Step 3: Multi-Image Product Analysis', 'No images selected - analysis will proceed without visual input.', '📷');
                }
        
                // Step 3.5: Mathematical BOM Calculations
                showLoading('🧮 Step 3.5/7: Calculating BOM mathematics using researched data...');
                try {
                    const mathData = await callAPI('/api/calculate-bom', {
                        imageAnalysis: analysisState.imageAnalysis
                    });
                    analysisState.calculatedBOM = mathData.result;
                    
                    const mathSummary = `Materials processed: ${mathData.materials_found}
                Total Weight: ${mathData.total_weight_lbs} lbs
                Total CO2 Footprint: ${mathData.result.totals.total_co2} kg CO2e
                
                CO2 Breakdown:
                - Sourcing: ${mathData.result.totals.total_sourcing_co2} kg (${mathData.result.calculation_summary.sourcing_percentage}%)
                - Manufacturing: ${mathData.result.totals.total_manufacturing_co2} kg (${mathData.result.calculation_summary.manufacturing_percentage}%)
                - Transport: ${mathData.result.totals.total_transport_co2} kg (${mathData.result.calculation_summary.transport_percentage}%)
                
                All calculations based on researched material properties from image analysis step.
                
                Detailed Results:
                ${JSON.stringify(mathData.result, null, 2)}`;
                    
                    addResult('Step 3.5: Mathematical BOM Calculations', mathSummary, '🧮');
                } catch (error) {
                    addResult('❌ Math Calculation Error', `Failed to calculate BOM mathematics: ${error.message}`, '❌');
                    // Continue with analysis even if math fails
                    analysisState.calculatedBOM = null;
                }
                
                // Step 4: Final Product Assessment (formerly Final BOM Table)
                showLoading('📊 Step 4/7: Creating final product assessment...');
                const countryOfOrigin = document.getElementById('country-of-origin-input').value.trim();
                
                const reconciliationData = await callAPI('/api/reconciliation', {
                    researchBOM: analysisState.productBOM,
                    imageAnalysis: analysisState.imageAnalysis,
                    calculatedBOM: analysisState.calculatedBOM ? JSON.stringify(analysisState.calculatedBOM) : null,
                    generalResearch: analysisState.generalResearch,
                    prompt: document.getElementById('reconciliation-prompt').value,
                    countryOfOrigin: countryOfOrigin // NEW: Pass the value to the backend
                });
                analysisState.finalBOM = reconciliationData.result;
                addResult('Step 4: Final Product Assessment', analysisState.finalBOM, '📊');
                
                // Step 5: Category and Lifespan
                showLoading('📂 Step 5/7: Analyzing categories...');
                const categoryData = await callAPI('/api/category', {
                    product: productName
                });
                addResult('Step 5: Product Category Analysis', categoryData.result, '📂');
                
                showLoading('⏰ Step 6/7: Analyzing lifespan...');
                const lifespanData = await callAPI('/api/lifespan', {
                    product: productName
                });
                addResult('Step 6: Product Lifespan Analysis', lifespanData.result, '⏰');
                
                hideLoading();
                setComplete();
                
            } catch (error) {
                hideLoading();
                addResult('❌ Error', error.message, '❌');
                setComplete();
            }
        }


    </script>
</body>
</html>
"""

def calculate_bom_math(materials_data, total_product_weight_lbs):
    """Calculate all mathematical BOM fields using volume percentages and material densities"""
    
    # Emission factors for different transport methods (kg CO2e per kg-km)
    # Keywords are lowercase for robust matching
    TRANSPORT_EMISSION_FACTORS = {
        "ocean": 0.000011, # Covers "Ocean Freight", "Shipping", etc.
        "air": 0.00113,   # Covers "Air Freight"
        "rail": 0.000025,  # Covers "Rail", "Rail Transport"
        "truck": 0.000098 # Covers "Truck", "Road"
    }
    DEFAULT_TRANSPORT_FACTOR = TRANSPORT_EMISSION_FACTORS["ocean"]

    try:
        results = []
        total_sourcing_co2 = 0
        total_manufacturing_co2 = 0
        total_transport_co2 = 0
        total_end_of_life_co2 = 0
        total_calculated_weight = 0
        total_volume_percentage = 0
        total_volume_density = 0
        
        # First pass: calculate all volume densities to get the total
        for material in materials_data:
            try:
                volume_percentage = float(material.get('volume_percentage', 0))
                density_lb_ft3 = float(material.get('density_lb_ft3', 0))
                material_volume_density = (volume_percentage / 100) * density_lb_ft3
                total_volume_density += material_volume_density
                total_volume_percentage += volume_percentage
            except (ValueError, TypeError) as e:
                raise Exception(f"Invalid numeric data for material {material.get('name', 'Unknown')}: {e}")
        
        if total_volume_density <= 0:
            raise Exception("Total volume density is zero or negative - check material densities")
        
        # Second pass: calculate actual weights using density distribution
        for material in materials_data:
            try:
                volume_percentage = float(material.get('volume_percentage', 0))
                density_lb_ft3 = float(material.get('density_lb_ft3', 0))
                material_volume_density = (volume_percentage / 100) * density_lb_ft3
                volume_density_percentage = (material_volume_density / total_volume_density * 100) if total_volume_density > 0 else 0
                material_weight_lbs = total_product_weight_lbs * (volume_density_percentage / 100)
                material_weight_kg = material_weight_lbs * 0.453592
                total_calculated_weight += material_weight_lbs
                
                co2_sourcing_rate = float(material.get('co2_sourcing_kg_per_kg', 0))
                co2_manufacturing_rate = float(material.get('co2_manufacturing_kg_per_kg', 0))
                distance_km = float(material.get('distance_km', 0))

                # --- ROBUST DYNAMIC TRANSPORT CALCULATION ---
                transport_method_str = material.get('transport_method', 'Ocean Freight').lower()
                co2_transport_rate = DEFAULT_TRANSPORT_FACTOR
                for keyword, factor in TRANSPORT_EMISSION_FACTORS.items():
                    if keyword in transport_method_str:
                        co2_transport_rate = factor
                        break
                
                # Calculate CO2 emissions
                sourcing_co2 = material_weight_kg * co2_sourcing_rate
                manufacturing_co2 = material_weight_kg * co2_manufacturing_rate
                transport_co2 = material_weight_kg * distance_km * co2_transport_rate
                end_of_life_co2 = material_weight_kg * 0.02
                total_material_co2 = sourcing_co2 + manufacturing_co2 + transport_co2 + end_of_life_co2
                
                total_sourcing_co2 += sourcing_co2
                total_manufacturing_co2 += manufacturing_co2
                total_transport_co2 += transport_co2
                total_end_of_life_co2 += end_of_life_co2
                
                result_material = {
                    'name': material.get('name', ''),
                    'volume_percentage': round(volume_percentage, 2),
                    'density_lb_ft3': round(density_lb_ft3, 4),
                    'material_volume_density': round(material_volume_density, 4),
                    'volume_density_percentage': round(volume_density_percentage, 2),
                    'material_weight_lbs': round(material_weight_lbs, 4),
                    'material_weight_kg': round(material_weight_kg, 4),
                    'source_country': material.get('source_country', ''),
                    'manufacturing_process': material.get('manufacturing_process', ''),
                    'distance_km': distance_km,
                    'co2_sourcing_kg_per_kg': co2_sourcing_rate,
                    'co2_manufacturing_kg_per_kg': co2_manufacturing_rate,
                    'co2_transport_kg_per_kg_km': co2_transport_rate,
                    'transport_method': material.get('transport_method', 'Ocean Freight'),
                    'sourcing_co2': round(sourcing_co2, 4),
                    'manufacturing_co2': round(manufacturing_co2, 4),
                    'transport_co2': round(transport_co2, 4),
                    'end_of_life_co2': round(end_of_life_co2, 4),
                    'total_material_co2': round(total_material_co2, 4)
                }
                results.append(result_material)
                
            except (ValueError, TypeError) as e:
                raise Exception(f"Error calculating data for material {material.get('name', 'Unknown')}: {e}")
        
        total_co2 = total_sourcing_co2 + total_manufacturing_co2 + total_transport_co2 + total_end_of_life_co2
        weight_difference = total_product_weight_lbs - total_calculated_weight
        
        return {
            'materials': results,
            'totals': {
                'product_weight_lbs': total_product_weight_lbs,
                'calculated_material_weight_lbs': round(total_calculated_weight, 4),
                'weight_difference_lbs': round(weight_difference, 4),
                'total_volume_percentage': round(total_volume_percentage, 4),
                'total_volume_density': round(total_volume_density, 4),
                'total_weight_kg': round(total_product_weight_lbs * 0.453592, 4),
                'total_sourcing_co2': round(total_sourcing_co2, 4),
                'total_manufacturing_co2': round(total_manufacturing_co2, 4),
                'total_transport_co2': round(total_transport_co2, 4),
                'total_end_of_life_co2': round(total_end_of_life_co2, 4),
                'total_co2': round(total_co2, 4),
                'materials_count': len(results)
            },
            'calculation_summary': {
                'sourcing_percentage': round((total_sourcing_co2 / total_co2 * 100) if total_co2 > 0 else 0, 2),
                'manufacturing_percentage': round((total_manufacturing_co2 / total_co2 * 100) if total_co2 > 0 else 0, 2),
                'transport_percentage': round((total_transport_co2 / total_co2 * 100) if total_co2 > 0 else 0, 2),
                'end_of_life_percentage': round((total_end_of_life_co2 / total_co2 * 100) if total_co2 > 0 else 0, 2),
                'volume_total_check': round(total_volume_percentage, 2),
                'density_accuracy': round(((total_calculated_weight / total_product_weight_lbs) * 100) if total_product_weight_lbs > 0 else 0, 2)
            }
        }
        
    except Exception as e:
        raise Exception(f"BOM calculation failed: {e}")

def extract_materials_from_image_analysis(image_analysis_text):
    """Extract researched materials data from image analysis JSON"""
    try:
        # Look for JSON block in the text
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', image_analysis_text, re.DOTALL)
        if not json_match:
            raise Exception("No JSON data found in image analysis. Please ensure the image analysis includes the required JSON output.")
        
        json_data = json.loads(json_match.group(1))
        materials = json_data.get('materials', [])
        total_weight = json_data.get('total_weight_lbs', 0)
        
        if not materials:
            raise Exception("No materials found in JSON data")
        
        if total_weight <= 0:
            raise Exception("Invalid total weight in JSON data")
        
        # Validate that volume percentages are present and sum to ~100%
        total_volume = 0
        for material in materials:
            if 'volume_percentage' not in material:
                raise Exception(f"Missing volume percentage for material: {material.get('name', 'Unknown')}")
            total_volume += float(material.get('volume_percentage', 0))
        
        if total_volume < 95 or total_volume > 105:
            raise Exception(f"Volume percentages sum to {total_volume}% - should be close to 100%")
        
        return materials, total_weight
        
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON format in image analysis: {e}")
    except Exception as e:
        raise Exception(f"Error extracting materials: {e}")

def call_perplexity_api(prompt):
    """Call Perplexity API"""
    if not PPLX_API_KEY:
        raise Exception("Perplexity API key not configured")
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PPLX_API_KEY}"
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a detailed analyst. Follow the instructions exactly. If asked for text analysis only, provide only text. If asked for tables, provide tables with methodology. Always provide complete data for all requested fields and calculations."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")
    
    return response.json()['choices'][0]['message']['content']

def call_claude_api(prompt):
    """Call Claude API"""
    if not ANTHROPIC_API_KEY:
        raise Exception("Claude API key not configured")
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "content-type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-sonnet-4-0",
        "max_tokens": 4000,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")
    
    return response.json()['content'][0]['text']

def call_openai_api(prompt):
    """Call OpenAI API"""
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a detailed analyst. Follow the instructions exactly. If asked for text analysis only, provide only text. If asked for tables, provide tables with methodology. Always provide complete data for all requested fields and calculations."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")
    
    return response.json()['choices'][0]['message']['content']

def call_gemini_api(prompt):
    """Call Google Gemini API"""
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key not configured")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0}
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Gemini API call failed: {response.status_code} - {response.text}")
    
    return response.json()['candidates'][0]['content']['parts'][0]['text']

# Vision API Functions
def call_openai_vision_api(prompt, image_url):
    """Call OpenAI GPT-4V API with image"""
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 3000,
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"OpenAI Vision API call failed: {response.status_code} - {response.text}")
    
    return response.json()['choices'][0]['message']['content']

def call_claude_vision_api(prompt, image_url):
    """Call Claude 3 Vision API with image"""
    if not ANTHROPIC_API_KEY:
        raise Exception("Claude API key not configured")
    
    # First, download the image and convert to base64
    try:
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            raise Exception(f"Failed to download image: {img_response.status_code}")
        
        # Convert to base64
        image_data = base64.b64encode(img_response.content).decode('utf-8')
        
        # Determine image type
        content_type = img_response.headers.get('content-type', 'image/jpeg')
        if 'png' in content_type:
            media_type = "image/png"
        elif 'gif' in content_type:
            media_type = "image/gif"
        elif 'webp' in content_type:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
            
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "content-type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 3000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    }
                ]
            }
        ],
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Claude Vision API call failed: {response.status_code} - {response.text}")
    
    return response.json()['content'][0]['text']

def call_llm_api(prompt, llm_choice, force_web_capable=False):
    """Call the appropriate LLM API based on choice"""
    print(f"call_llm_api called with: llm_choice={llm_choice}, force_web_capable={force_web_capable}")
    
    # For research steps that need web access, always use web-capable models
    if force_web_capable and llm_choice == 'openai':
        print("Forcing web-capable model, switching from openai to perplexity")
        llm_choice = 'perplexity'  # Fallback to Perplexity for web access
    
    print(f"Final LLM choice: {llm_choice}")
    
    if llm_choice == 'perplexity':
        print("Calling Perplexity API")
        return call_perplexity_api(prompt)
    elif llm_choice == 'claude':
        print("Calling Claude API")
        return call_claude_api(prompt)
    elif llm_choice == 'openai':
        print("Calling OpenAI API")
        return call_openai_api(prompt)
    elif llm_choice == 'gemini':
        print("Calling Gemini API")
        return call_gemini_api(prompt)
    elif llm_choice == 'serpapi':
        print("Calling SerpAPI")
        return call_serpapi_search(prompt)
    else:
        raise Exception(f"Unknown LLM choice: {llm_choice}")


def call_serpapi_search(prompt):
    """Call SerpAPI for direct Google search"""
    if not SERPAPI_KEY:
        raise Exception("SerpAPI key not configured")
    
    # Extract product name from the prompt
    import re
    
    # Look for the product name after "URL SEARCH FOR:"
    product_match = re.search(r'URL SEARCH FOR:\s*(.+?)(?:\n|$)', prompt)
    if product_match:
        search_query = product_match.group(1).strip()
    else:
        # Fallback: look for quoted search terms
        search_matches = re.findall(r'"([^"]*)"', prompt)
        if search_matches:
            search_query = search_matches[0]
        else:
            # Last resort: use first line as search query
            search_query = prompt.split('\n')[0][:100]
    
    print(f"SerpAPI extracted search query: {search_query}")
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": SERPAPI_KEY,
        "num": 10
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"SerpAPI request failed: {response.status_code}")
    
    data = response.json()
    results = []
    
    # Format organic results with more detail for URL finding
    for result in data.get('organic_results', [])[:8]:
        results.append(f"""
SEARCH RESULT:
Title: {result.get('title', '')}
URL: {result.get('link', '')}
Snippet: {result.get('snippet', '')}
---""")
    
    return f"""Google Search Results for: {search_query}

VERIFIED PRODUCT URLS FOUND:
{chr(10).join(results)}

Note: The above URLs were found via Google search for "{search_query}". 
Please verify these are correct product pages and extract specifications."""



@app.route('/')
def index():
    # Scan the directory for template files
    template_files = []
    if os.path.exists(RESEARCH_TEMPLATE_DIR):
        template_files = [f for f in os.listdir(RESEARCH_TEMPLATE_DIR) if f.endswith('.txt')]

    return render_template_string(HTML_TEMPLATE, 
                                research_prompt=DEFAULT_RESEARCH_PROMPT,
                                product_prompt=DEFAULT_PRODUCT_PROMPT.format(url_prompt=DEFAULT_URL_PROMPT),
                                image_prompt=DEFAULT_IMAGE_PROMPT,
                                reconciliation_prompt=DEFAULT_RECONCILIATION_PROMPT,
                                url_prompt=DEFAULT_URL_PROMPT,
                                research_templates=template_files) # Pass the list to the template

# New API endpoint to fetch a template's content
@app.route('/api/get-research-template/<filename>')
def get_research_template(filename):
    try:
        # Security: ensure filename is safe
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': 'Invalid filename'}), 400

        filepath = os.path.join(RESEARCH_TEMPLATE_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({'content': content})
        else:
            return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-images', methods=['POST'])
def search_images_api():
    data = request.json
    product = data.get('product')
    
    if not SERPAPI_KEY:
        return jsonify({'error': 'SerpAPI key not configured. Please set SERPAPI_KEY environment variable.'}), 500
    
    try:
        # Search for product images using SerpAPI
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_images",
            "q": f'"{product}" product -pinterest -ebay -amazon -etsy',
            "api_key": SERPAPI_KEY,
            "num": 8,  # Get 8 images
            "safe": "active"
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return jsonify({'error': f'SerpAPI request failed: {response.status_code}'}), 500
        
        data = response.json()
        images = []
        
        # Extract image results
        for img in data.get('images_results', [])[:6]:  # Limit to 6 images
            images.append({
                'url': img.get('original'),
                'thumbnail': img.get('thumbnail'),
                'title': img.get('title', ''),
                'source': img.get('source', '')
            })
        
        return jsonify({'images': images})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Image analysis using vision models
@app.route('/api/image-analysis', methods=['POST'])
def image_analysis_api():
    data = request.json
    image_url = data.get('imageUrl')
    product_bom = data.get('productBOM', '')
    prompt = data.get('prompt')
    vision_llm = data.get('visionLLM', 'openai')
    
    if not image_url:
        return jsonify({'error': 'No image URL provided'}), 400
    
    # Construct the full prompt with context
    full_prompt = f"""PRODUCT BOM ANALYSIS CONTEXT:
{product_bom}

IMAGE ANALYSIS TASK:
{prompt}

Please analyze the provided image and compare it to the BOM analysis above."""
    
    try:
        if vision_llm == 'openai':
            result = call_openai_vision_api(full_prompt, image_url)
        elif vision_llm == 'claude':
            result = call_claude_vision_api(full_prompt, image_url)
        elif vision_llm == 'perplexity':
            # Perplexity fallback - use OpenAI if available
            result = call_openai_vision_api(full_prompt, image_url)
        else:
            return jsonify({'error': f'Unknown vision LLM: {vision_llm}'}), 400
            
        return jsonify({'result': result})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/research', methods=['POST'])
def research_api():
    data = request.json
    product = data.get('product')
    prompt = data.get('prompt')
    llm_choice = data.get('llm', 'perplexity')
    
    full_prompt = f"For the following product: {product} {prompt}"
    
    try:
        # Research always needs web access, so force web-capable models
        result = call_llm_api(full_prompt, llm_choice, force_web_capable=True)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/product-bom', methods=['POST'])
def product_bom_api():
    data = request.json
    product = data.get('product')
    prompt = data.get('prompt')
    general_research = data.get('generalResearch', '')
    url_results = data.get('urlResults', '')  # NEW: Get URL results
    llm_choice = data.get('llm', 'perplexity')
    
    full_prompt = f"""GENERAL PRODUCT KNOWLEDGE (Use this as your PRIMARY reference for materials and components):
{'='*80}
{general_research}
{'='*80}

URL SEARCH RESULTS (from Step 2a):
{'='*80}
{url_results}
{'='*80}

NOW ANALYZE THIS SPECIFIC PRODUCT:
Product: {product}
{'='*80}

IMPORTANT: The general knowledge above contains the comprehensive list of materials and components typical for this product category. 
Use it as your foundation and the URL search results to adjust percentages based on this specific product's features.

{prompt}"""
    
    try:
        # Product analysis doesn't need web access since URLs already retrieved
        result = call_llm_api(full_prompt, llm_choice, force_web_capable=False)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reconciliation', methods=['POST'])
def reconciliation_api():
    data = request.json
    research_bom = data.get('researchBOM', '')
    image_analysis = data.get('imageAnalysis', '')
    calculated_bom = data.get('calculatedBOM', '')
    general_research = data.get('generalResearch', '')
    prompt = data.get('prompt')
    llm_choice = data.get('llm', 'perplexity')
    country_of_origin = data.get('countryOfOrigin', '')

    current_date = datetime.now().strftime('%B %d, %Y')
    prompt_with_date = prompt.replace('[Current date]', current_date)

    # This logic remains to ensure the user-specified country is used in the report text
    override_instruction = ""
    if country_of_origin:
        override_instruction = f"**USER OVERRIDE:** The user has specified the Country of Origin as **'{country_of_origin}'**. You MUST use this value for the 'Country of Origin' field in the assessment, overriding any country found during your own research.\n\n"
        prompt_with_date = prompt_with_date.replace('[Manufacturing country from research]', country_of_origin)
    
    # The header and system boundary are no longer changed, ensuring they always refer to the full ...to-USA journey

    full_prompt = f"""{override_instruction}GENERAL PRODUCT KNOWLEDGE:
{general_research}

PRODUCT BOM ANALYSIS:
{research_bom}

IMAGE ANALYSIS FINDINGS:
{image_analysis}

CALCULATED MATHEMATICAL DATA (Use this for all quantitative values):
{calculated_bom}

{prompt_with_date}"""
    
    try:
        result = call_llm_api(full_prompt, llm_choice, force_web_capable=False)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/category', methods=['POST'])
def category_api():
    data = request.json
    product = data.get('product')
    llm_choice = data.get('llm', 'perplexity')
    
    prompt = f"""For the following product: {product} Follow the below steps:
Create an Excel style table of product categories based on the Amazon listing, using the following formatting as a guide: 
Department, Category, Subcategory, Specific Category. 
Add a final column that shows the type of product within the specific category by analyzing the different product types available.
Hide the explanation"""
    
    try:
        # Category analysis needs web access for Amazon lookup
        result = call_llm_api(prompt, llm_choice, force_web_capable=True)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/lifespan', methods=['POST'])
def lifespan_api():
    data = request.json
    product = data.get('product')
    llm_choice = data.get('llm', 'perplexity')
    
    prompt = f"""For the following: {product} Follow the below steps:
For the general types of this Product's Category, estimate their lifespan in one number of years where lifetime is equal to 100 years, and display results in an table format including a column that displays the specific product category.
Hide the steps and explanation"""
    
    try:
        # Lifespan analysis doesn't necessarily need web access, use selected LLM
        result = call_llm_api(prompt, llm_choice, force_web_capable=False)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-claude', methods=['GET'])
def debug_claude():
    try:
        # Simple test call
        result = call_claude_api("Just say 'API key works'")
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/multi-image-analysis', methods=['POST'])
def multi_image_analysis_api():
    data = request.json
    image_urls = data.get('imageUrls', [])
    product_bom = data.get('productBOM', '')
    prompt = data.get('prompt')
    vision_llm = data.get('visionLLM', 'openai')
    # 👇 NEW: Accepts the country of origin, defaulting to 'USA' if not provided
    country_of_origin = data.get('countryOfOrigin', 'USA') 
    
    if not image_urls or len(image_urls) == 0:
        return jsonify({'error': 'No image URLs provided'}), 400
    
    first_image_url = image_urls[0]
    
    # 👇 UPDATED: The prompt is now formatted with the correct country of origin
    full_prompt = f"""PRODUCT BOM ANALYSIS CONTEXT:
{product_bom}

MULTI-IMAGE ANALYSIS TASK:
{prompt.format(country_of_origin=country_of_origin)}

You are analyzing {len(image_urls)} images of the same product. Please provide a comprehensive assessment based on the visual evidence.

Images provided: {len(image_urls)} product images from different angles."""
    
    try:
        if vision_llm == 'openai':
            result = call_openai_vision_api(full_prompt, first_image_url)
        elif vision_llm == 'claude':
            result = call_claude_vision_api(full_prompt, first_image_url)
        elif vision_llm == 'perplexity':
            result = call_openai_vision_api(full_prompt, first_image_url)
        else:
            return jsonify({'error': f'Unknown vision LLM: {vision_llm}'}), 400
            
        return jsonify({'result': result})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/manual-url-test', methods=['POST'])
def manual_url_test_api():
    data = request.json
    product = data.get('product')
    urls = data.get('urls', [])
    prompt = data.get('prompt', '')
    
    if not urls:
        return jsonify({'error': 'No URLs provided'}), 400
    
    # Format the manual URLs for analysis
    url_list = "\n".join([f"URL {i+1}: {url}" for i, url in enumerate(urls)])
    
    result = f"""Manual URL Analysis for: {product}

MANUALLY PROVIDED URLS:
{url_list}

ANALYSIS INSTRUCTIONS:
{prompt}

**VERIFIED PRODUCT URLS FOUND:**
- **Primary URL:** {urls[0] if len(urls) > 0 else 'Not provided'}
- **Secondary URL:** {urls[1] if len(urls) > 1 else 'Not provided'}  
- **Additional URL:** {urls[2] if len(urls) > 2 else 'Not provided'}

**MANUAL URL SUMMARY:**
- Total URLs provided: {len(urls)}
- URLs ready for analysis: {len(urls)}
- Source: Manual user input

Note: These URLs were manually provided by the user. Please visit each URL to extract detailed product specifications, weight, dimensions, materials, and other relevant information for the BOM analysis."""
    
    try:
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/url-search-test', methods=['POST'])
def url_search_test_api():
    data = request.json
    product = data.get('product')
    prompt = data.get('prompt')
    llm_choice = data.get('llm', 'perplexity')
    
    # ADD LOGGING
    print(f"=== URL SEARCH TEST DEBUG ===")
    print(f"Product: {product}")
    print(f"LLM Choice: {llm_choice}")
    print(f"Full request data: {data}")
    
    try:
        result = call_llm_api(prompt, llm_choice, force_web_capable=True)
        print(f"Result length: {len(result)} characters")
        print(f"Result preview: {result[:200]}...")
        return jsonify({'result': result})
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-bom', methods=['POST'])
def calculate_bom_api():
    data = request.json
    image_analysis = data.get('imageAnalysis', '')
    
    if not image_analysis:
        return jsonify({'error': 'No image analysis data provided'}), 400
    
    try:
        # Extract materials from image analysis with researched properties
        materials, total_weight_from_earlier_steps = extract_materials_from_image_analysis(image_analysis)
        
        if not materials:
            return jsonify({'error': 'No materials found in image analysis. Please ensure the image analysis includes material data with research.'}), 400
        
        if total_weight_from_earlier_steps <= 0:
            return jsonify({'error': 'Invalid total weight from earlier steps. Please ensure URL analysis provided valid product weight.'}), 400
        
        # Debug: Log the extracted data
        print(f"DEBUG: Extracted {len(materials)} materials, total weight: {total_weight_from_earlier_steps} lbs")
        for i, material in enumerate(materials):
            print(f"  Material {i+1}: {material.get('name', 'Unknown')} - Volume: {material.get('volume_percentage', 0)}%, Density: {material.get('density_lb_ft3', 0)} lb/ft³")
        
        # Calculate all mathematical fields using researched data and provided total weight
        calculated_bom = calculate_bom_math(materials, total_weight_from_earlier_steps)
        
        # Prepare response with detailed breakdown
        response_data = {
            'result': calculated_bom,
            'materials_found': len(materials),
            'total_weight_lbs': total_weight_from_earlier_steps,
            'calculated_weight_lbs': calculated_bom['totals']['calculated_material_weight_lbs'],
            'calculation_status': 'success',
            'data_sources': 'All calculations based on researched material properties from image analysis step and total weight from product research'
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"ERROR in calculate_bom_api: {str(e)}")
        return jsonify({
            'error': str(e),
            'calculation_status': 'failed',
            'suggestion': 'Ensure the image analysis step completed successfully and includes the required JSON output with researched material properties including volumes',
            'debug_info': f'Image analysis length: {len(image_analysis)} characters'
        }), 500

if __name__ == '__main__':
    print("Starting TraceLogic.AI Flask Application...")
    print("\nAccess the application at: http://localhost:7860")
    
    import os
    port = int(os.environ.get('PORT', 7860))
    app.run(debug=False, host='0.0.0.0', port=port)
