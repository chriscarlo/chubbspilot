import math

from cereal import car
from opendbc.can.parser import CANParser
from openpilot.selfdrive.car.interfaces import RadarInterfaceBase
from openpilot.selfdrive.car.hyundai.hyundaicanfd import CanBus
from openpilot.selfdrive.car.hyundai.values import DBC, HyundaiFlags, HyundaiFlagsCP, CANFD_CAR

RADAR_START_ADDR = 0x500
RADAR_MSG_COUNT = 32

# POC for parsing corner radars: https://github.com/commaai/openpilot/pull/24221/

def get_radar_can_parser(CP):
  if DBC[CP.carFingerprint]['radar'] is None:
    if CP.carFingerprint in CANFD_CAR:
      if CP.flags & HyundaiFlagsCP.FP_CAMERA_SCC_LEAD:
        lead_src, bus = "SCC_CONTROL", CanBus(CP).CAM
      else:
        return None
    else:
      if CP.flags & HyundaiFlagsCP.FP_CAMERA_SCC_LEAD:
        lead_src, bus = "SCC11", 2
      else:
        return None
    messages = [(lead_src, 50)]
    return CANParser(DBC[CP.carFingerprint]['pt'], messages, bus)

  messages = [(f"RADAR_TRACK_{addr:x}", 50) for addr in range(RADAR_START_ADDR, RADAR_START_ADDR + RADAR_MSG_COUNT)]
  return CANParser(DBC[CP.carFingerprint]['radar'], messages, 1)

def get_corner_radar_can_parser(CP):
  # TODO: investigate radar_track DBC for corner radar messages
  messages_fd = [
    # Metadata on FD bus (129)
    ("RADAR_POINTS_METADATA_0x100", 50),  # Left metadata
    ("RADAR_POINTS_METADATA_0x200", 50),  # Right metadata
    # Checksum on FD bus (129)
    ("RADAR_POINTS_CHECKSUM_0x104", 50),  # Left checksum
    ("RADAR_POINTS_CHECKSUM_0x204", 50),  # Right checksum
  ]
  messages_pt = [
    # Points on PT bus (0)
    ("RADAR_POINTS_0x101", 50),  # Left corner points
    ("RADAR_POINTS_0x201", 50),  # Right corner points
  ]
  # Add messages for front corner radar from CANFD DBC
  messages_canfd = [
    ("BLINDSPOTS_FRONT_CORNER_1", 50),    # Front corner radar 1
    ("BLINDSPOTS_FRONT_CORNER_2", 50),    # Front corner radar 2
  ]
  # Metadata on FD bus (129)
  parser_fd = CANParser(DBC[CP.carFingerprint]['corner_radar'], messages_fd, 129)
  # Points on PT bus (0) - note bus 130 appears to mirror bus 0
  parser_pt = CANParser(DBC[CP.carFingerprint]['corner_radar'], messages_pt, 0)
  # Front corner radar messages on CANFD bus
  parser_canfd = CANParser(DBC[CP.carFingerprint]['pt'], messages_canfd, 5)
  return parser_fd, parser_pt, parser_canfd

class RadarInterface(RadarInterfaceBase):
  def __init__(self, CP):
    super().__init__(CP)
    self.CP = CP
    self.camera_scc = CP.flags & HyundaiFlagsCP.FP_CAMERA_SCC_LEAD
    self.updated_messages = set()
    self.trigger_msg = 0x1A0 if self.camera_scc and CP.carFingerprint in CANFD_CAR else \
                       0x420 if self.camera_scc else \
                       (RADAR_START_ADDR + RADAR_MSG_COUNT - 1)
    self.track_id = 0

    self.radar_off_can = CP.radarUnavailable
    self.rcp = get_radar_can_parser(CP)
    if CP.flags & HyundaiFlags.CORNER_RADAR:
      self.corner_rcp_fd, self.corner_rcp_pt, self.corner_rcp_canfd = get_corner_radar_can_parser(CP)
    else:
      self.corner_rcp_fd = None
      self.corner_rcp_pt = None
      self.corner_rcp_canfd = None
    self.fp_radar_tracks = CP.flags & HyundaiFlagsCP.ENABLE_RADAR_TRACKS

  def update(self, can_strings):
    if self.radar_off_can or (self.rcp is None):
      return super().update(None)

    vls = self.rcp.update_strings(can_strings)
    self.updated_messages.update(vls)

    if self.trigger_msg not in self.updated_messages:
      return None

    rr = self._update(self.updated_messages)
    self.updated_messages.clear()

    radar_error = []
    if rr is not None:
      radar_error = rr.errors
    if list(radar_error) and self.fp_radar_tracks:
      return super().update(can_strings)

    # Process corner radar messages
    if self.corner_rcp_fd and self.corner_rcp_pt and self.corner_rcp_canfd:
      # Update all parsers
      corner_vls_fd = self.corner_rcp_fd.update_strings(can_strings)
      corner_vls_pt = self.corner_rcp_pt.update_strings(can_strings)
      corner_vls_canfd = self.corner_rcp_canfd.update_strings(can_strings)

      # Process corner radar points
      corner_points = {}

      # Get metadata first (point count etc)
      metadata = {}
      for msg_name in corner_vls_fd:
        if msg_name.startswith("RADAR_POINTS_METADATA"):
          metadata[msg_name] = self.corner_rcp_fd.vl[msg_name]

      for msg_name in corner_vls_pt:
        if msg_name.startswith("RADAR_POINTS_0x"):
          points = self.corner_rcp_pt.vl[msg_name]

          # Get corresponding metadata
          meta_msg = f"RADAR_POINTS_METADATA_0x{msg_name[-3:]}"
          if meta_msg not in metadata:
            continue

          meta = metadata[meta_msg]
          point_count = meta.get('RADAR_POINT_COUNT', 0)

          # Process each valid point
          for i in range(1, min(6, point_count + 1)):  # Max 5 points per corner
            if points.get(f'POINT_{i}_DISTANCE', 0) > 0:  # Only process valid points
              corner_points[f"{msg_name}_{i}"] = {
                'dRel': points[f'POINT_{i}_DISTANCE'] * 0.015625,  # Apply scaling from DBC
                'yRel': points[f'POINT_{i}_AZIMUTH'] * 0.001953125,  # Apply scaling from DBC
                'vRel': (points[f'POINT_{i}_REL_VELOCITY'] * 0.03125) - 66,  # Apply scaling and offset from DBC
              }

      # Process front corner radar points
      if "BLINDSPOTS_FRONT_CORNER_1" in corner_vls_canfd:
        front_corner_1 = self.corner_rcp_canfd.vl["BLINDSPOTS_FRONT_CORNER_1"]
        if front_corner_1.get('NEW_SIGNAL_1', 0) > 0:  # Vehicle detected
          corner_points['front_left'] = {
            'detected': True,
            'approaching': front_corner_1.get('NEW_SIGNAL_2', 0) > 0
          }

      if "BLINDSPOTS_FRONT_CORNER_2" in corner_vls_canfd:
        front_corner_2 = self.corner_rcp_canfd.vl["BLINDSPOTS_FRONT_CORNER_2"]
        if front_corner_2.get('NEW_SIGNAL_1', 0) > 0:  # Vehicle detected
          corner_points['front_right'] = {
            'detected': True,
            'approaching': front_corner_2.get('NEW_SIGNAL_2', 0) > 0
          }

      # Store processed corner radar data
      rr.corner_radar_points = corner_points

    return rr

  def _update(self, updated_messages):
    ret = car.RadarData.new_message()
    if self.rcp is None:
      return ret

    errors = []

    if not self.rcp.can_valid:
      errors.append("canError")
    ret.errors = errors

    if self.camera_scc:
      msg_src = "SCC_CONTROL" if self.CP.carFingerprint in CANFD_CAR else \
                "SCC11"
      msg = self.rcp.vl[msg_src]
      valid = msg['ACC_ObjDist'] < 240 if self.CP.carFingerprint in CANFD_CAR else \
              msg['ACC_ObjStatus']
      for ii in range(1):
        if valid:
          if ii not in self.pts:
            self.pts[ii] = car.RadarData.RadarPoint.new_message()
            self.pts[ii].trackId = self.track_id
            self.track_id += 1
          self.pts[ii].measured = True
          self.pts[ii].dRel = msg['ACC_ObjDist'] * 1.1
          self.pts[ii].yRel = float('nan')
          self.pts[ii].vRel = msg['ACC_ObjRelSpd']
          self.pts[ii].aRel = float('nan')
          self.pts[ii].yvRel = float('nan')

        else:
          if ii in self.pts:
            del self.pts[ii]
    else:
     for addr in range(RADAR_START_ADDR, RADAR_START_ADDR + RADAR_MSG_COUNT):
        msg = self.rcp.vl[f"RADAR_TRACK_{addr:x}"]

        if addr not in self.pts:
            self.pts[addr] = car.RadarData.RadarPoint.new_message()
            self.pts[addr].trackId = self.track_id
            self.track_id += 1

        valid = msg['STATE'] in (3, 4)
        if valid:
            azimuth = math.radians(msg['AZIMUTH'])
            self.pts[addr].measured = True
            self.pts[addr].dRel = math.cos(azimuth) * msg['LONG_DIST']
            self.pts[addr].yRel = 0.5 * -math.sin(azimuth) * msg['LONG_DIST']
            self.pts[addr].vRel = msg['REL_SPEED']
            self.pts[addr].aRel = msg['REL_ACCEL']
            self.pts[addr].yvRel = float('nan')

        else:
            del self.pts[addr]

    # Add corner radar data to points if available
    # Track ID ranges:
    # 0-999: Main forward radar
    # 1000-1999: Rear left corner radar
    # 2000-2999: Rear right corner radar
    # 3000-3999: Front left corner radar
    # 4000-4999: Front right corner radar
    if hasattr(self, 'corner_rcp_fd') and hasattr(self, 'corner_rcp_pt') and \
       self.corner_rcp_fd is not None and self.corner_rcp_pt is not None:

      # Get metadata first (point count etc)
      metadata = {}
      for msg_name in self.corner_rcp_fd.vl:
        if msg_name.startswith("RADAR_POINTS_METADATA"):
          metadata[msg_name] = self.corner_rcp_fd.vl[msg_name]

      # Process rear left and right corner radar points
      for msg_name in self.corner_rcp_pt.vl:
        if msg_name.startswith("RADAR_POINTS_0x"):
          points = self.corner_rcp_pt.vl[msg_name]

          # Get corresponding metadata
          meta_msg = f"RADAR_POINTS_METADATA_0x{msg_name[-3:]}"
          if meta_msg not in metadata:
            continue

          meta = metadata[meta_msg]
          point_count = meta.get('RADAR_POINT_COUNT', 0)

          # Determine if this is left (0x1) or right (0x2) rear corner radar
          base_id = 1000 if "0x1" in msg_name else 2000  # 1000 for left, 2000 for right

          # Process each valid point
          for i in range(1, min(6, point_count + 1)):  # Max 5 points per corner
            if points.get(f'POINT_{i}_DISTANCE', 0) > 0:  # Only process valid points
              corner_id = base_id + i  # Simple indexing within each range

              if corner_id not in self.pts:
                self.pts[corner_id] = car.RadarData.RadarPoint.new_message()
                self.pts[corner_id].trackId = corner_id

              # Scale values according to DBC
              self.pts[corner_id].measured = True
              self.pts[corner_id].dRel = points[f'POINT_{i}_DISTANCE'] * 0.015625
              self.pts[corner_id].yRel = points[f'POINT_{i}_AZIMUTH'] * 0.001953125
              self.pts[corner_id].vRel = (points[f'POINT_{i}_REL_VELOCITY'] * 0.03125) - 66
              self.pts[corner_id].aRel = float('nan')
              self.pts[corner_id].yvRel = float('nan')

      # Process front corner radar points
      if self.corner_rcp_canfd:
        # Front left corner radar
        if "BLINDSPOTS_FRONT_CORNER_1" in self.corner_rcp_canfd.vl:
          front_corner_1 = self.corner_rcp_canfd.vl["BLINDSPOTS_FRONT_CORNER_1"]
          if front_corner_1.get('NEW_SIGNAL_1', 0) > 0:  # Vehicle detected
            front_left_id = 3000  # Base ID for front left corner

            if front_left_id not in self.pts:
              self.pts[front_left_id] = car.RadarData.RadarPoint.new_message()
              self.pts[front_left_id].trackId = front_left_id

            self.pts[front_left_id].measured = True
            # These values are simplified since we don't have detailed measurements
            # Adjust with real values if available in the CAN message
            self.pts[front_left_id].dRel = 10.0  # Placeholder distance
            self.pts[front_left_id].yRel = -2.0  # Left side
            self.pts[front_left_id].vRel = 0.0 if not front_corner_1.get('NEW_SIGNAL_2', 0) else -5.0  # Approaching
            self.pts[front_left_id].aRel = float('nan')
            self.pts[front_left_id].yvRel = float('nan')

        # Front right corner radar
        if "BLINDSPOTS_FRONT_CORNER_2" in self.corner_rcp_canfd.vl:
          front_corner_2 = self.corner_rcp_canfd.vl["BLINDSPOTS_FRONT_CORNER_2"]
          if front_corner_2.get('NEW_SIGNAL_1', 0) > 0:  # Vehicle detected
            front_right_id = 4000  # Base ID for front right corner

            if front_right_id not in self.pts:
              self.pts[front_right_id] = car.RadarData.RadarPoint.new_message()
              self.pts[front_right_id].trackId = front_right_id

            self.pts[front_right_id].measured = True
            # These values are simplified since we don't have detailed measurements
            # Adjust with real values if available in the CAN message
            self.pts[front_right_id].dRel = 10.0  # Placeholder distance
            self.pts[front_right_id].yRel = 2.0   # Right side
            self.pts[front_right_id].vRel = 0.0 if not front_corner_2.get('NEW_SIGNAL_2', 0) else -5.0  # Approaching
            self.pts[front_right_id].aRel = float('nan')
            self.pts[front_right_id].yvRel = float('nan')

    ret.points = list(self.pts.values())
    return ret
