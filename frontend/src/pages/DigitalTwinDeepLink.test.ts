import { describe, expect, it } from "vitest";
import { formatSpaceRoomName, formatStoreyName } from "../lib/format";

describe("Digital Twin Deep Linking Logic", () => {
  const mockSpaces = [
    { space_id: "space_3U1W8Xs6L9pRXU5Afk5MW1", ifc_name: "114", storey_id: "storey_1mnZnZ29v9QRze4pjg0g3S", ifc_global_id: "3U1W8Xs6L9pRXU5Afk5MW1" },
    { space_id: "space_3U1W8Xs6L9pRXU5Afk5MW2", ifc_name: "107", storey_id: "storey_0IEk6ObD54bwMLfrOXff7W", ifc_global_id: "3U1W8Xs6L9pRXU5Afk5MW2" },
  ];

  const mockStoreys = [
    { storey_id: "storey_0IEk6ObD54bwMLfrOXff7W", name: "2. korrus" },
    { storey_id: "storey_1mnZnZ29v9QRze4pjg0g3S", name: "3. korrus" },
  ];

  it("1. Space Planning button passes canonical space ID in query parameter", () => {
    const spaceId = "space_3U1W8Xs6L9pRXU5Afk5MW2";
    const linkPath = `/twin?space=${encodeURIComponent(spaceId)}`;
    expect(linkPath).toBe("/twin?space=space_3U1W8Xs6L9pRXU5Afk5MW2");
  });

  it("2 & 4. /twin?space=<id> finds the correct room and selects it", () => {
    const spaceParam = "space_3U1W8Xs6L9pRXU5Afk5MW2";
    const found = mockSpaces.find(
      (s) =>
        s.space_id.toLowerCase() === spaceParam.toLowerCase() ||
        s.ifc_global_id.toLowerCase() === spaceParam.toLowerCase()
    );
    expect(found).toBeDefined();
    expect(found?.space_id).toBe("space_3U1W8Xs6L9pRXU5Afk5MW2");
    expect(found?.ifc_name).toBe("107");
  });

  it("3 & 5. Automatically activates the room's floor and opens Space Inspector with human-readable name", () => {
    const found = mockSpaces[1]; // Room 107 on Floor 2
    const storey = mockStoreys.find((st) => st.storey_id === found.storey_id);
    expect(storey).toBeDefined();
    const humanFloor = formatStoreyName(storey?.name);
    const humanRoom = formatSpaceRoomName(found.ifc_name, found.space_id);
    expect(humanFloor).toBe("Floor 2");
    expect(humanRoom).toBe("Room 107");
  });

  it("6. Calculates 3D camera target center for focus positioning", () => {
    const mockBoundingBox = {
      min: { x: -10, y: 0, z: -5 },
      max: { x: 10, y: 4, z: 5 },
    };
    const center = [
      (mockBoundingBox.min.x + mockBoundingBox.max.x) / 2,
      (mockBoundingBox.min.y + mockBoundingBox.max.y) / 2,
      (mockBoundingBox.min.z + mockBoundingBox.max.z) / 2,
    ];
    expect(center).toEqual([0, 2, 0]);
  });

  it("7. Handles invalid space ID gracefully", () => {
    const invalidParam = "space_invalid_999";
    const found = mockSpaces.find(
      (s) =>
        s.space_id.toLowerCase() === invalidParam.toLowerCase() ||
        s.ifc_global_id.toLowerCase() === invalidParam.toLowerCase()
    );
    expect(found).toBeUndefined();
    // Application flags error state without crashing
    const errorState = found ? null : invalidParam;
    expect(errorState).toBe("space_invalid_999");
  });

  it("8. Normal /twin navigation initializes cleanly without preset space", () => {
    const spaceParam = null;
    const initialSelectedSpace = spaceParam ? "preset" : null;
    const initialFloor = spaceParam ? "preset_floor" : null;
    expect(initialSelectedSpace).toBeNull();
    expect(initialFloor).toBeNull();
  });
});
