"""Official Central Pollution Control Board (CPCB) National Air Quality Index (NAQI) Breakpoints.

Source: Central Pollution Control Board, Ministry of Environment, Forest and Climate Change,
Government of India - "National Air Quality Index" Report (October 2014 / 2015 revisions).
"""

from typing import Dict, List, NamedTuple


class BreakpointRange(NamedTuple):
    c_low: float      # Concentration lower bound
    c_high: float     # Concentration upper bound
    i_low: int        # AQI sub-index lower bound
    i_high: int       # AQI sub-index upper bound
    category: str     # CPCB AQI Category


# AQI Categories and official color codes & health statements
AQI_CATEGORIES = {
    "GOOD": {
        "range": (0, 50),
        "color": "#10B981",  # Emerald / Green
        "description": "Minimal impact",
        "advisory": "Air quality is considered satisfactory, and air pollution poses little or no risk.",
    },
    "SATISFACTORY": {
        "range": (51, 100),
        "color": "#84CC16",  # Lime
        "description": "Minor breathing discomfort to sensitive people",
        "advisory": "Air quality is acceptable; however, very sensitive people may experience minor irritation.",
    },
    "MODERATE": {
        "range": (101, 200),
        "color": "#EAB308",  # Amber / Yellow
        "description": "Breathing discomfort to the people with lungs, asthma and heart diseases",
        "advisory": "Children and adults with respiratory or cardiac conditions should limit prolonged outdoor exertion.",
    },
    "POOR": {
        "range": (201, 300),
        "color": "#F97316",  # Orange
        "description": "Breathing discomfort to most people on prolonged exposure",
        "advisory": "Everyone should reduce heavy outdoor exertion. Sensitive groups should avoid extended outdoor activity.",
    },
    "VERY_POOR": {
        "range": (301, 400),
        "color": "#EF4444",  # Red
        "description": "Respiratory illness on prolonged exposure",
        "advisory": "Avoid strenuous outdoor activities. Wear protective masks (N95) when outdoors.",
    },
    "SEVERE": {
        "range": (401, 500),
        "color": "#7F1D1D",  # Dark Maroon
        "description": "Affects healthy people and seriously impacts those with existing diseases",
        "advisory": "Emergency conditions. Remain indoors, keep windows closed, and operate air purifiers.",
    },
}


# Official CPCB Breakpoints for 8 criteria pollutants
# Concentrations are in µg/m³ except CO which is in mg/m³
CPCB_BREAKPOINTS: Dict[str, List[BreakpointRange]] = {
    "pm10": [  # 24-hr avg in µg/m³
        BreakpointRange(0, 50, 0, 50, "GOOD"),
        BreakpointRange(51, 100, 51, 100, "SATISFACTORY"),
        BreakpointRange(101, 250, 101, 200, "MODERATE"),
        BreakpointRange(251, 350, 201, 300, "POOR"),
        BreakpointRange(351, 430, 301, 400, "VERY_POOR"),
        BreakpointRange(431, 500, 401, 500, "SEVERE"),
    ],
    "pm25": [  # 24-hr avg in µg/m³
        BreakpointRange(0, 30, 0, 50, "GOOD"),
        BreakpointRange(31, 60, 51, 100, "SATISFACTORY"),
        BreakpointRange(61, 90, 101, 200, "MODERATE"),
        BreakpointRange(91, 120, 201, 300, "POOR"),
        BreakpointRange(121, 250, 301, 400, "VERY_POOR"),
        BreakpointRange(251, 350, 401, 500, "SEVERE"),
    ],
    "no2": [  # 24-hr avg in µg/m³
        BreakpointRange(0, 40, 0, 50, "GOOD"),
        BreakpointRange(41, 80, 51, 100, "SATISFACTORY"),
        BreakpointRange(81, 180, 101, 200, "MODERATE"),
        BreakpointRange(181, 280, 201, 300, "POOR"),
        BreakpointRange(281, 400, 301, 400, "VERY_POOR"),
        BreakpointRange(401, 500, 401, 500, "SEVERE"),
    ],
    "o3": [  # 8-hr avg in µg/m³
        BreakpointRange(0, 50, 0, 50, "GOOD"),
        BreakpointRange(51, 100, 51, 100, "SATISFACTORY"),
        BreakpointRange(101, 168, 101, 200, "MODERATE"),
        BreakpointRange(169, 208, 201, 300, "POOR"),
        BreakpointRange(209, 748, 301, 400, "VERY_POOR"),
        BreakpointRange(749, 1000, 401, 500, "SEVERE"),
    ],
    "co": [  # 8-hr avg in mg/m³
        BreakpointRange(0.0, 1.0, 0, 50, "GOOD"),
        BreakpointRange(1.1, 2.0, 51, 100, "SATISFACTORY"),
        BreakpointRange(2.1, 10.0, 101, 200, "MODERATE"),
        BreakpointRange(10.1, 17.0, 201, 300, "POOR"),
        BreakpointRange(17.1, 34.0, 301, 400, "VERY_POOR"),
        BreakpointRange(34.1, 50.0, 401, 500, "SEVERE"),
    ],
    "so2": [  # 24-hr avg in µg/m³
        BreakpointRange(0, 40, 0, 50, "GOOD"),
        BreakpointRange(41, 80, 51, 100, "SATISFACTORY"),
        BreakpointRange(81, 380, 101, 200, "MODERATE"),
        BreakpointRange(381, 800, 201, 300, "POOR"),
        BreakpointRange(801, 1600, 301, 400, "VERY_POOR"),
        BreakpointRange(1601, 2000, 401, 500, "SEVERE"),
    ],
    "nh3": [  # 24-hr avg in µg/m³
        BreakpointRange(0, 200, 0, 50, "GOOD"),
        BreakpointRange(201, 400, 51, 100, "SATISFACTORY"),
        BreakpointRange(401, 800, 101, 200, "MODERATE"),
        BreakpointRange(801, 1200, 201, 300, "POOR"),
        BreakpointRange(1201, 1800, 301, 400, "VERY_POOR"),
        BreakpointRange(1801, 2400, 401, 500, "SEVERE"),
    ],
    "pb": [  # 24-hr avg in µg/m³
        BreakpointRange(0.0, 0.5, 0, 50, "GOOD"),
        BreakpointRange(0.51, 1.0, 51, 100, "SATISFACTORY"),
        BreakpointRange(1.01, 2.0, 101, 200, "MODERATE"),
        BreakpointRange(2.01, 3.0, 201, 300, "POOR"),
        BreakpointRange(3.01, 3.5, 301, 400, "VERY_POOR"),
        BreakpointRange(3.51, 5.0, 401, 500, "SEVERE"),
    ],
}


# Educational metadata for pollutants
POLLUTANT_INFO = {
    "pm25": {
        "name": "Particulate Matter ≤ 2.5 µm",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "Fine particles that can penetrate deep into the lungs and enter the bloodstream.",
        "primary_sources": "Vehicular exhaust, biomass burning, industrial combustion, construction dust.",
        "health_effects": "Aggravates asthma, decreases lung function, exacerbates respiratory and cardiovascular disease.",
    },
    "pm10": {
        "name": "Particulate Matter ≤ 10 µm",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "Inhalable coarse particles capable of irritating respiratory airways and eyes.",
        "primary_sources": "Road dust, construction and demolition, stone crushing, agricultural soil tilling.",
        "health_effects": "Coughing, wheezing, bronchitis, and worsening of chronic respiratory conditions.",
    },
    "no2": {
        "name": "Nitrogen Dioxide",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "A reddish-brown gas resulting from high-temperature fuel combustion.",
        "primary_sources": "Internal combustion vehicle engines, thermal power plants, industrial boilers.",
        "health_effects": "Airway inflammation, heightened susceptibility to respiratory infections, triggers asthma.",
    },
    "so2": {
        "name": "Sulphur Dioxide",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "A pungent, reactive gas primarily released during coal and oil burning.",
        "primary_sources": "Coal-fired power generation, metal smelting, chemical manufacturing refineries.",
        "health_effects": "Constriction of airways, severe eye irritation, and acute bronchospasm in asthmatics.",
    },
    "co": {
        "name": "Carbon Monoxide",
        "unit": "mg/m³",
        "averaging_period": "8 hours",
        "description": "Colorless, odorless gas formed by incomplete combustion of carbon-based fuels.",
        "primary_sources": "Incomplete vehicle fuel combustion, brick kilns, unvented kerosene heaters.",
        "health_effects": "Reduces oxygen delivery to body organs and tissues, causes dizziness and headaches.",
    },
    "o3": {
        "name": "Ground-Level Ozone",
        "unit": "µg/m³",
        "averaging_period": "8 hours",
        "description": "Secondary pollutant formed when NOx and VOCs chemically react in the presence of sunlight.",
        "primary_sources": "Atmospheric photochemical reactions between vehicle exhaust and volatile organic compounds.",
        "health_effects": "Chest tightness, reduced breathing capacity, throat irritation, lung tissue damage.",
    },
    "nh3": {
        "name": "Ammonia",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "A corrosive alkaline gas contributing heavily to secondary particulate formation.",
        "primary_sources": "Agricultural fertilizers, animal manure, waste decomposing, chemical plants.",
        "health_effects": "Upper respiratory tract irritation, coughing, eye burning, throat burning.",
    },
    "pb": {
        "name": "Lead",
        "unit": "µg/m³",
        "averaging_period": "24 hours",
        "description": "Heavy metal pollutant persistent in the environment.",
        "primary_sources": "Battery recycling, metal smelters, leaded industrial paints, historical residues.",
        "health_effects": "Neurological toxicity, developmental impairment in children, renal damage.",
    },
}
