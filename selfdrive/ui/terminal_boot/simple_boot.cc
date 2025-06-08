// Simplified boot UI for TICI wide screen
#include <iostream>
#include <string>
#include <thread>
#include <chrono>

int main() {
  // Simple centered logo without ANSI codes that might not work
  std::string pad(100, ' ');  // Rough center for 2160px wide screen
  
  std::cout << "\n\n\n\n\n\n\n\n\n\n";  // Vertical centering
  std::cout << pad << "CHAUFFEUR\n";
  std::cout << pad << "AUTONOMOUS DRIVING SYSTEM v2.0\n";
  std::cout << pad << "INITIALIZING...\n";
  std::cout << std::endl;
  
  // Read and echo status updates
  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty()) {
      std::cout << pad << "[*] " << line << std::endl;
    }
  }
  
  return 0;
}