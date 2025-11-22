# Azure VM Standard Pricing via API

This note summarizes how to pull **standard (retail) Azure Virtual Machine pricing** programmatically.

---

## 1. API Overview

Azure publishes retail (pay‑as‑you‑go) prices through the **Azure Retail Prices REST API**.

- **Base endpoint**  
  `https://prices.azure.com/api/retail/prices`

- **Optional API version parameter**  
  `api-version=2023-01-01-preview`

This API is:
- Public (no auth needed for list pricing)
- Read‑only
- Focused on *retail* prices (not your custom discounts or EA rates).

---

## 2. Key Fields for VM Pricing

When you query VM pricing, each record typically includes (among others):

- `serviceName` – e.g., `"Virtual Machines"`  
- `serviceFamily` – e.g., `"Compute"`  
- `productName` – human‑readable description (series/OS/etc.)  
- `skuName` – commercial SKU identifier  
- `armSkuName` – ARM resource SKU (e.g. `Standard_D2s_v3`)  
- `armRegionName` – Azure region (e.g. `eastus`)  
- `retailPrice` – current retail price  
- `unitPrice` – price per unit (often same as `retailPrice` for hourly)  
- `unitOfMeasure` – e.g. `"1 Hour"`  
- `currencyCode` – e.g. `"USD"`  
- `meterName`, `meterId`, `type`, `effectiveStartDate`, etc.

---

## 3. Basic Query Pattern

You filter results using an OData `filter` parameter.

### 3.1 Filter Only VM Pricing

```text
GET https://prices.azure.com/api/retail/prices
    ?api-version=2023-01-01-preview
    &$filter=serviceName eq 'Virtual Machines'
```

### 3.2 Filter by Region and SKU

Example for **Standard_D2s_v3 in East US**:

```text
GET https://prices.azure.com/api/retail/prices
    ?api-version=2023-01-01-preview
    &$filter=serviceName eq 'Virtual Machines'
        and armRegionName eq 'eastus'
        and armSkuName eq 'Standard_D2s_v3'
```

### 3.3 Common Filters for VM Pricing

- `serviceName eq 'Virtual Machines'`
- `armRegionName eq '<region>'` (e.g. `eastus`, `westus2`, `westeurope`)
- `armSkuName eq '<SKU>'` (e.g. `Standard_B2ms`, `Standard_E4_v5`)
- `priceType eq 'Consumption'` (for pay‑as‑you‑go)
- `skuName` and `productName` can be used for additional constraints.

You can combine filters with `and`. For string values, use single quotes.

---

## 4. Pagination

The API returns up to ~1000 records per page. The JSON response contains:

- `Items` – array of price records
- `NextPageLink` – URL for the next page (if any)

High‑level paging loop:

1. Call the endpoint with your filter.
2. Process `Items`.
3. If `NextPageLink` is not null, call that URL to fetch the next page.
4. Repeat until `NextPageLink` is null.

---

## 5. Example cURL

### 5.1 List All VM Retail Prices (US Dollar)

```bash
curl "https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20'Virtual%20Machines'"
```

### 5.2 Single SKU & Region

```bash
curl "https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20'Virtual%20Machines'%20and%20armRegionName%20eq%20'eastus'%20and%20armSkuName%20eq%20'Standard_D2s_v3'"
```

(Spaces are URL‑encoded as `%20`.)

---

## 6. Example Python Snippet

```python
import requests

BASE_URL = "https://prices.azure.com/api/retail/prices"
FILTER = (
    "serviceName eq 'Virtual Machines' "
    "and armRegionName eq 'eastus' "
    "and armSkuName eq 'Standard_D2s_v3' "
    "and priceType eq 'Consumption'"
)

params = {
    "$filter": FILTER,
    "api-version": "2023-01-01-preview",
}

items = []
url = BASE_URL

while url:
    resp = requests.get(url, params=params if url == BASE_URL else None)
    resp.raise_for_status()
    data = resp.json()

    items.extend(data.get("Items", []))
    url = data.get("NextPageLink")  # None when finished

# Example: print SKU, region, price
for item in items:
    print(
        item.get("armSkuName"),
        item.get("armRegionName"),
        item.get("retailPrice"),
        item.get("unitOfMeasure"),
        item.get("currencyCode"),
    )
```

You can easily adapt this to:
- Export to CSV
- Feed into a cost modeling tool
- Populate a database for further analysis.

---

## 7. Important Caveats

1. **Retail pricing only**  
   - This API exposes public list prices (pay‑as‑you‑go).  
   - It **does not** reflect your discounts (EA, MCA, CSP, reservations, savings plan, etc.).

2. **VM price dimensions**  
   - Different meters exist for Linux, Windows, Spot, reserved terms, etc.  
   - Filter on `productName`, `meterName`, and `skuName` carefully if you need a specific OS or purchase model.

3. **Regions & currency**  
   - Pricing varies by region and currency.  
   - For multi‑region modeling, be explicit about `armRegionName` and `currencyCode`.

4. **Changes over time**  
   - `effectiveStartDate` indicates when a price record became active.  
   - For historical cost modeling, you may need to account for price changes over time.

---

## 8. Suggested Usage Pattern (for a FinOps or DevFinOps Tool)

1. Build a **small abstraction** around the Retail Prices API:
   - Input: region, VM SKU, OS, purchase type (On‑Demand/Spot/Reserved).  
   - Output: normalized `price_per_hour` (and maybe per month @ 730 hours).

2. Cache results in a local DB (e.g., DuckDB/Postgres) so you’re not hammering the API.

3. Use the cached prices to power:
   - Optimization recommendations (e.g., right‑sizing, region moves).  
   - Unit economics calculations.  
   - “What‑if” analyses (e.g., change VM size, region, OS).

This file is meant to be a concise reference so you can quickly wire up Azure VM retail pricing into scripts, CLIs, or FinOps tooling.
