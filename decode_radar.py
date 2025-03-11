import binascii

def get_bits(data, start_bit, length):
    """Extract bits from a byte array.

    Args:
        data: Bytes to extract from
        start_bit: Starting bit position from left (0 = MSB)
        length: Number of bits to extract

    Returns:
        Integer value of extracted bits
    """
    val = int.from_bytes(data, 'big')
    mask = (1 << length) - 1
    shift = (len(data) * 8) - start_bit - length
    return (val >> shift) & mask

def decode_point(hex_str):
    """Decode a corner radar point from its hex string representation.

    Message format:
    - Distance: 14 bits starting at bit 7, scaling 0.0015625 cm/bit
    - Velocity: 13 bits starting at bit 31, zero point at 1241
    - Azimuth: 12 bits starting at bit 48, scaling 0.1 degrees - 45

    Args:
        hex_str: Hex string containing the radar point data

    Returns:
        Dictionary containing raw and decoded values
    """
    data = binascii.unhexlify(hex_str)

    # Extract raw values
    distance_raw = get_bits(data, 7, 14)   # 14 bits starting at bit 7
    velocity_raw = get_bits(data, 31, 13)  # 13 bits starting at bit 31
    azimuth_raw = get_bits(data, 48, 12)   # 12 bits starting at bit 48

    # Print raw values for debugging
    print(f"\nRaw binary values:")
    print(f"Distance: {distance_raw:014b} ({distance_raw})")
    print(f"Velocity: {velocity_raw:013b} ({velocity_raw})")
    print(f"Azimuth:  {azimuth_raw:012b} ({azimuth_raw})")
    print("\nFirst 8 bytes as hex:")
    print(' '.join(f"{x:02x}" for x in data[:8]))

    # Apply verified scaling factors
    distance_cm = distance_raw * 0.0015625  # Gives ~21.7cm at 13877
    velocity_mps = (velocity_raw - 1241) * 0.03125  # Zero at 1241
    azimuth_deg = (azimuth_raw * 0.1) - 45  # Gives ~90° range centered at 0

    return {
        "raw": {
            "distance": distance_raw,
            "velocity": velocity_raw,
            "azimuth": azimuth_raw
        },
        "decoded": {
            "distance_cm": distance_cm,
            "distance_m": distance_cm / 100,
            "velocity_mps": velocity_mps,
            "velocity_kph": velocity_mps * 3.6,
            "azimuth_deg": azimuth_deg
        }
    }

# Test data from parked car
test_data = [
    "1fb1afa64d9b360da64d03000000000000000000000000000000000000000000",
    "5b01b0a64d9b360da64d03000000000000000000000000000000000000000000",
    "1d58b1a64d9b360da64d03000000000000000000000000000000000000000000",
    "d7b3b2a64d9b360da64d03000000000000000000000000000000000000000000",
    "91eab3a64d9b360da64d03000000000000000000000000000000000000000000",
    "6274b4a64d9b360da64d03000000000000000000000000000000000000000000"
]

for i, data in enumerate(test_data):
    print(f"\nPoint {i+1}:")
    result = decode_point(data)
    decoded = result['decoded']

    print("\nDecoded values:")
    print(f"Distance: {decoded['distance_cm']:.2f} cm ({decoded['distance_m']:.3f} m)")
    print(f"Velocity: {decoded['velocity_mps']:.2f} m/s ({decoded['velocity_kph']:.1f} km/h)")
    print(f"Azimuth:  {decoded['azimuth_deg']:.3f}°")