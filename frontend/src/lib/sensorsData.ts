// CampusIQ — Human-readable sensor metadata and presentation helpers.
// Maps raw telemetry sensor UUIDs to human-friendly operational names.

const DEVICE_PRIMARY_TYPE: Record<string, string> = {
  "04f80f82-e206-427c-a913-69758a1ec283": "Temperature Sensor",
  "065931eb-3930-492c-ac91-85a0936fcf82": "Building Energy Meter",
  "08e2d921-2317-4642-b003-90bc1fce878a": "PM2.5 Air Quality Sensor",
  "2522f700-8446-4619-9399-23b97d077209": "Climate Sensor (Temp/RH)",
  "2cc97dbf-8e73-475b-a2e7-cecdb74e7838": "Main Power Meter",
  "33281c95-d69f-4611-a0c7-38790e115426": "Sub-Station Energy Meter",
  "37b7c0e4-9943-489e-98a9-2ab4796a7d94": "Climate Sensor (Temp/RH)",
  "3ca720cf-53ac-4326-9c09-c435c4d4e13a": "Distribution Energy Meter",
  "421151cb-043f-4ccc-844d-ff94cd659f2b": "Climate Sensor (Temp/RH)",
  "42cb320d-b911-4648-bb65-f0d54984551d": "Climate Sensor (Temp/RH)",
  "4565853e-95df-4027-8b05-82d26bf6eec1": "Climate Sensor (Temp/RH)",
  "45f91780-63fc-4d24-bf64-0e42c440fca5": "Temperature Sensor",
  "4dcb026e-d888-4e84-9892-6e81d487a214": "Climate Sensor (Temp/RH)",
  "6690d4cb-bb58-47a8-b0f8-be2e99056be0": "Climate Sensor (Temp/RH)",
  "76824528-d7e4-423b-b818-8f900b41d6fb": "Climate Sensor (Temp/RH)",
  "79c625d4-2530-4332-903e-82d480563c75": "Climate Sensor (Temp/RH)",
  "7a0b43e6-7a9b-48bc-84b8-feddd15131c5": "Climate Sensor (Temp/RH)",
  "81845c1a-5a2c-43eb-a443-8276649abb67": "Climate Sensor (Temp/RH)",
  "8af61c3a-e76f-45cb-abae-504c208d0ccb": "Climate Sensor (Temp/RH)",
  "99ca72a1-36de-4e79-b65d-16cdec7e42fb": "IAQ Sensor (CO₂/Temp/RH)",
  "9a7e9493-2411-4213-a65b-1372023e02d3": "PM2.5 Air Quality Sensor",
  "9b662d91-8343-46b6-848a-9c190d6d46b7": "Climate Sensor (Temp/RH)",
  "a6bbc801-c605-4782-8d17-111c606cf662": "Climate Sensor (Temp/RH)",
  "ad03002a-9ba7-4b0a-b055-2e981dfa95a2": "Climate Sensor (Temp/RH)",
  "c6f4d193-bab8-438a-8706-d2f60e0ef81b": "IAQ Sensor (CO₂/Temp/RH)",
  "d2948a1d-b2a0-435b-a9f6-abe67df61b70": "IAQ Sensor (CO₂/Temp/RH)",
  "d77ac61a-ca38-4030-810e-738161f81c7e": "Climate Sensor (Temp/RH)",
  "d9a2275e-351a-4095-9e35-7cae87c0112f": "IAQ Sensor (CO₂/Temp/RH)",
  "dfd7a151-1cae-4cd6-b3af-91ff110a21b2": "Climate Sensor (Temp/RH)",
  "e0f66126-28e9-4681-bf89-9ecccd961997": "Climate Sensor (Temp/RH)",
  "e4373caf-650d-40e9-8f12-ec47d40eb1c2": "Temperature Sensor",
  "e720f446-3626-4318-a136-079529b57492": "PM2.5 Air Quality Sensor",
  "f4a76a84-7b19-4f32-a681-3eabdaeaaabe": "IAQ Sensor (CO₂/Temp/RH)",
  "f5c3c0e6-cf08-439f-8d31-fc739c100455": "IAQ Sensor (CO₂/Temp/RH)",
  "f776d51d-bd6c-40a9-8af7-58142934ee9f": "Climate Sensor (Temp/RH)",
  "fa54ef81-7df5-41e7-a5e8-5d97a69dc151": "IAQ Sensor (CO₂/Temp/RH)",
};

const MEASUREMENT_NAMES: Record<string, string> = {
  co2: "CO₂ Sensor",
  carbon_dioxide: "CO₂ Sensor",
  temperature: "Temperature Sensor",
  humidity: "Humidity Sensor",
  relative_humidity: "Humidity Sensor",
  "pm2.5": "PM2.5 Sensor",
  pm25: "PM2.5 Sensor",
  energy: "Energy Meter",
  power: "Power Meter",
};

/**
 * Returns a human-friendly sensor name.
 * e.g. "PM2.5 Sensor", "CO₂ Sensor", "Climate Sensor (Temp/RH)"
 */
export function getSensorDisplayName(
  sensorId?: string | null,
  measurementType?: string | null,
): string {
  if (measurementType) {
    const key = measurementType.toLowerCase().trim();
    if (MEASUREMENT_NAMES[key]) return MEASUREMENT_NAMES[key];
  }

  if (sensorId && DEVICE_PRIMARY_TYPE[sensorId]) {
    return DEVICE_PRIMARY_TYPE[sensorId];
  }

  if (measurementType) {
    return `${measurementType.charAt(0).toUpperCase() + measurementType.slice(1)} Sensor`;
  }

  return "Campus Environmental Sensor";
}

/**
 * Maps technical health issue codes to human-readable explanations.
 */
export function formatIssueName(issueType: string): string {
  const norm = issueType.toUpperCase().trim();
  switch (norm) {
    case "CONSTANT_VALUE":
      return "Constant-value behavior";
    case "IRREGULAR_SAMPLING":
      return "Irregular sampling";
    case "LONG_GAP":
    case "LONG_DATA_GAP":
      return "Long data gap";
    case "EXCESSIVE_MISSING":
      return "High missing data rate";
    case "OUT_OF_BOUNDS":
      return "Out-of-bounds readings";
    default:
      return norm.replace(/[_-]+/g, " ").toLowerCase();
  }
}

/**
 * Human-readable location description.
 */
export function formatLocation(status?: string | null, spaceName?: string | null): string {
  if (spaceName && spaceName !== "—") return spaceName;
  if (status === "VERIFIED_BIM") {
    return "Verified room";
  }
  return "Not assigned to an individual room";
}

/**
 * Recommendation text for sensor health issues.
 */
export function getSensorRecommendation(issues: string[], healthStatus?: string): string {
  if (healthStatus === "HEALTHY") {
    return "Operating normally within baseline parameters.";
  }
  if (issues.includes("CONSTANT_VALUE")) {
    return "Inspect sensor data stream and probe connection.";
  }
  if (issues.includes("LONG_GAP")) {
    return "Verify gateway transmission and polling schedule.";
  }
  if (issues.includes("IRREGULAR_SAMPLING")) {
    return "Inspect power supply stability and packet delivery.";
  }
  return "Inspect sensor data stream.";
}
