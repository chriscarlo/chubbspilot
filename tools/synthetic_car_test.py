#!/usr/bin/env python3
"""
Synthetic car data generator for testing without real car data or routes
"""

import os
import sys
import time
import numpy as np
from typing import Optional

# Add openpilot to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import cereal.messaging as messaging
from cereal import car, log
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper

class SyntheticCarData:
    """Generate synthetic car data for testing"""
    
    def __init__(self, fingerprint: str = "HONDA_CIVIC_2022"):
        self.fingerprint = fingerprint
        self.pm = messaging.PubMaster(['can', 'carState', 'carControl', 'controlsState'])
        self.frame = 0
        
        # Initialize parameters
        self.speed = 0.0  # m/s
        self.angle = 0.0  # steering wheel angle
        self.gas = 0.0
        self.brake = 0.0
        
    def generate_can_messages(self):
        """Generate synthetic CAN messages"""
        # This would normally come from the car
        dat = messaging.new_message('can', 1)
        dat.can = []
        return dat
    
    def generate_car_state(self):
        """Generate synthetic car state"""
        msg = messaging.new_message('carState')
        cs = msg.carState
        
        # Basic vehicle state
        cs.vEgo = self.speed
        cs.vEgoCluster = self.speed * 3.6  # km/h
        cs.steeringAngleDeg = self.angle
        cs.steeringRateDeg = 0.0
        cs.gas = self.gas
        cs.gasPressed = self.gas > 0
        cs.brake = self.brake
        cs.brakePressed = self.brake > 0
        cs.brakeLights = cs.brakePressed
        
        # Cruise state
        cs.cruiseState.enabled = False
        cs.cruiseState.available = True
        cs.cruiseState.speed = 30.0  # m/s
        
        # Gear
        cs.gearShifter = car.CarState.GearShifter.drive
        
        # Doors
        cs.doorOpen = False
        cs.seatbeltUnlatched = False
        
        # Steering
        cs.steeringTorque = 0.0
        cs.steeringPressed = False
        
        # ESP
        cs.espDisabled = False
        
        return msg
    
    def simulate_driving_scenario(self, scenario: str = "cruise"):
        """Simulate different driving scenarios"""
        
        rk = Ratekeeper(100)  # 100Hz
        
        print(f"Running synthetic test scenario: {scenario}")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                self.frame += 1
                
                # Update state based on scenario
                if scenario == "cruise":
                    # Steady cruise at 25 m/s (90 km/h)
                    self.speed = 25.0
                    self.angle = np.sin(self.frame * 0.01) * 5  # Gentle weaving
                    
                elif scenario == "accel":
                    # Accelerating
                    self.speed = min(30.0, self.speed + 0.1)
                    self.gas = 0.5
                    
                elif scenario == "brake":
                    # Braking
                    self.speed = max(0.0, self.speed - 0.2)
                    self.brake = 0.7
                    
                elif scenario == "curve":
                    # Taking a curve
                    self.speed = 15.0
                    self.angle = 45.0 * np.sin(self.frame * 0.02)
                
                # Publish messages
                self.pm.send('can', self.generate_can_messages())
                self.pm.send('carState', self.generate_car_state())
                
                # Print status every second
                if self.frame % 100 == 0:
                    print(f"Frame {self.frame}: Speed={self.speed:.1f} m/s, "
                          f"Angle={self.angle:.1f}°, Gas={self.gas:.1f}, Brake={self.brake:.1f}")
                
                rk.keep_time()
                
        except KeyboardInterrupt:
            print("\nStopped synthetic data generation")

def test_with_synthetic_data():
    """Example of how to use synthetic data for testing"""
    
    # Set up environment
    os.environ['FINGERPRINT'] = 'HONDA_CIVIC_2022'
    os.environ['PASSIVE'] = '0'
    os.environ['NOBOARD'] = '1'
    os.environ['SIMULATION'] = '1'
    
    # Create synthetic data generator
    synth = SyntheticCarData()
    
    print("\nAvailable scenarios:")
    print("1. cruise - Steady cruise with gentle steering")
    print("2. accel - Acceleration test")
    print("3. brake - Braking test")
    print("4. curve - Curve handling")
    
    # Run a scenario
    synth.simulate_driving_scenario("cruise")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate synthetic car data for testing')
    parser.add_argument('--scenario', choices=['cruise', 'accel', 'brake', 'curve'], 
                       default='cruise', help='Driving scenario to simulate')
    parser.add_argument('--fingerprint', default='HONDA_CIVIC_2022', 
                       help='Car fingerprint to use')
    
    args = parser.parse_args()
    
    # Create generator with specified car
    synth = SyntheticCarData(args.fingerprint)
    synth.simulate_driving_scenario(args.scenario)