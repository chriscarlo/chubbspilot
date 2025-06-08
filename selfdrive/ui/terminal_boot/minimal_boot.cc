// Minimal boot UI that definitely works on TICI
#include <iostream>
#include <string>
#include <unistd.h>

int main() {
  // Clear screen
  std::cout << "\033[2J\033[H";
  
  // Simple centered text for 2160x1080 display
  // Assuming ~8px per char, that's ~270 chars wide
  std::string pad(110, ' ');  // Center padding
  
  std::cout << "\n\n\n\n\n\n\n\n\n\n";  // Vertical centering
  
  // Simple ASCII logo without fancy characters
  std::cout << pad << "CHAUFFEUR\n";
  std::cout << pad << "AUTONOMOUS DRIVING SYSTEM\n";
  std::cout << pad << "=======================\n\n";
  
  std::cout << pad << "INITIALIZING...\n\n";
  
  // Read and display status updates from stdin
  std::string line;
  int count = 0;
  while (std::getline(std::cin, line)) {
    if (!line.empty()) {
      std::cout << pad << "[" << ++count << "] " << line << std::endl;
    }
  }
  
  return 0;
}