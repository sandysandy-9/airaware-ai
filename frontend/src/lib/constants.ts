export const AQI_CATEGORY_META = {
  GOOD: {
    label: "Good",
    range: "0 – 50",
    color: "#10B981",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
    textColor: "text-emerald-400",
    badgeColor: "bg-emerald-500 text-slate-950",
    description: "Minimal health impact. Air quality poses little to no risk.",
  },
  SATISFACTORY: {
    label: "Satisfactory",
    range: "51 – 100",
    color: "#84CC16",
    bgColor: "bg-lime-500/10",
    borderColor: "border-lime-500/30",
    textColor: "text-lime-400",
    badgeColor: "bg-lime-500 text-slate-950",
    description: "Acceptable air quality. Minor breathing discomfort to unusually sensitive individuals.",
  },
  MODERATE: {
    label: "Moderate",
    range: "101 – 200",
    color: "#EAB308",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
    textColor: "text-amber-400",
    badgeColor: "bg-amber-500 text-slate-950",
    description: "Breathing discomfort to sensitive cohorts (asthma, heart disease, elderly, children).",
  },
  POOR: {
    label: "Poor",
    range: "201 – 300",
    color: "#F97316",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
    textColor: "text-orange-400",
    badgeColor: "bg-orange-500 text-white",
    description: "Breathing discomfort to most people on prolonged outdoor exposure.",
  },
  VERY_POOR: {
    label: "Very Poor",
    range: "301 – 400",
    color: "#EF4444",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
    textColor: "text-red-400",
    badgeColor: "bg-red-500 text-white",
    description: "Respiratory illness on prolonged exposure. Severe risk for vulnerable populations.",
  },
  SEVERE: {
    label: "Severe",
    range: "401 – 500+",
    color: "#7F1D1D",
    bgColor: "bg-red-950/20",
    borderColor: "border-red-800/40",
    textColor: "text-red-300",
    badgeColor: "bg-red-900 text-white border border-red-700",
    description: "Public health emergency. Affects healthy people and severely impacts those with disease.",
  },
};

export const POPULAR_CITIES = [
  { id: "delhi", name: "New Delhi", state: "Delhi", lat: 28.6139, lon: 77.2090 },
  { id: "mumbai", name: "Mumbai", state: "Maharashtra", lat: 19.0760, lon: 72.8777 },
  { id: "bengaluru", name: "Bengaluru", state: "Karnataka", lat: 12.9716, lon: 77.5946 },
  { id: "kolkata", name: "Kolkata", state: "West Bengal", lat: 22.5726, lon: 88.3639 },
  { id: "chennai", name: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { id: "hyderabad", name: "Hyderabad", state: "Telangana", lat: 17.3850, lon: 78.4867 },
  { id: "ahmedabad", name: "Ahmedabad", state: "Gujarat", lat: 23.0225, lon: 72.5714 },
  { id: "pune", name: "Pune", state: "Maharashtra", lat: 18.5204, lon: 73.8567 },
  { id: "lucknow", name: "Lucknow", state: "Uttar Pradesh", lat: 26.8467, lon: 80.9462 },
  { id: "jaipur", name: "Jaipur", state: "Rajasthan", lat: 26.9124, lon: 75.7873 },
  { id: "patna", name: "Patna", state: "Bihar", lat: 25.5941, lon: 85.1376 },
  { id: "chandigarh", name: "Chandigarh", state: "Punjab/Haryana", lat: 30.7333, lon: 76.7794 },
];

export const ACTIVITY_OPTIONS = [
  { id: "walking", label: "Walking & Leisure", icon: "Footprints" },
  { id: "running", label: "Running & Jogging", icon: "Flame" },
  { id: "cycling", label: "Cycling & Cardio", icon: "Bike" },
  { id: "commuting", label: "Transit & Commute", icon: "Car" },
  { id: "outdoor_sports", label: "Outdoor Sports", icon: "Trophy" },
  { id: "indoor", label: "Indoor & Home Office", icon: "Home" },
];

export const VULNERABILITY_OPTIONS = [
  { id: "general", label: "General Healthy Adult", desc: "No known respiratory or cardiac risks" },
  { id: "children", label: "Children (< 14 years)", desc: "Developing respiratory tract, higher respiration rate" },
  { id: "elderly", label: "Elderly Adults (60+)", desc: "Reduced lung compliance, vulnerable cardiovascular system" },
  { id: "respiratory", label: "Asthma / COPD / Respiratory", desc: "Hyper-reactive airways, high broncho-constriction risk" },
  { id: "cardiovascular", label: "Heart & Vascular Condition", desc: "Risk of systemic arterial inflammation and ischemia" },
  { id: "pregnant", label: "Pregnant Individuals", desc: "Particulate placental barrier considerations" },
];

export const DURATION_OPTIONS = [
  { id: "<30m", label: "Brief (< 30 mins)" },
  { id: "30-60m", label: "Standard (30 – 60 mins)" },
  { id: "1-2h", label: "Extended (1 – 2 hours)" },
  { id: ">2h", label: "Prolonged (> 2 hours)" },
];

export const SUGGESTED_QUESTIONS = [
  "What does the current AQI mean for my health?",
  "Which pollutant is contributing most right now?",
  "Is outdoor running advisable under these conditions?",
  "What protective precautions should sensitive groups take?",
  "How does this location compare to Mumbai or Bengaluru?",
  "What are the typical emission sources of the dominant pollutant?",
];
