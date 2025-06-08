#include "selfdrive/ui/terminal_boot/terminal_ui.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <algorithm>
#include <cctype>

TerminalBootUI::TerminalBootUI() : progress_percentage(0), current_phase("INITIALIZING") {
  boot_start = std::chrono::steady_clock::now();
  
  // Initialize core services
  services["thermald"] = ServiceInfo{"thermald", "Thermal Manager", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["pandad"] = ServiceInfo{"pandad", "CAN Interface", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["camerad"] = ServiceInfo{"camerad", "Camera System", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["sensord"] = ServiceInfo{"sensord", "Sensor Interface", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["modeld"] = ServiceInfo{"modeld", "Vision Model", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["controlsd"] = ServiceInfo{"controlsd", "Vehicle Control", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["plannerd"] = ServiceInfo{"plannerd", "Path Planning", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["radard"] = ServiceInfo{"radard", "Radar Processing", ServiceStatus::PENDING, "", "", "", 0, ""};
  services["ui"] = ServiceInfo{"ui", "User Interface", ServiceStatus::PENDING, "", "", "", 0, ""};
}

TerminalBootUI::~TerminalBootUI() {
  // Restore cursor and clear formatting
  std::cout << SHOW_CURSOR << COLOR_RESET << std::endl;
}

void TerminalBootUI::init() {
  // Clear screen and hide cursor
  std::cout << CLEAR_SCREEN << CURSOR_HOME << HIDE_CURSOR;
  
  // Force flush to ensure terminal commands are processed
  std::cout.flush();
  
  // Get system info (would come from hardware module in real implementation)
  platform = "COMMA TICI (larch64)";
  serial = "CCF123456789";
  imei = "359876543210987";
  
  // Set terminal to UTF-8 mode
  std::cout << "\033%G";
  std::cout.flush();
}

void TerminalBootUI::drawHeader() {
  std::cout << CURSOR_HOME;
  
  // Center the logo for wide screens
  // TICI screen is 2160x1080, assume ~270 chars wide at standard font
  int screen_width = 270;  // Approximate character width
  std::string logo_line1 = "▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓";
  int logo_width = 56;  // Width of logo in characters
  int padding = (screen_width - logo_width) / 2;
  std::string pad(padding > 0 ? padding : 0, ' ');
  
  std::cout << COLOR_SALMON << STYLE_BOLD;
  std::cout << pad << "▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓\n";
  std::cout << pad << "▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓  ▓\n";
  std::cout << pad << "▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓\n";
  std::cout << pad << "▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓\n";
  std::cout << pad << "▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓ \n";
  std::cout << pad << "▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓ \n";
  std::cout << pad << "▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓\n";
  std::cout << pad << "▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓\n";
  
  std::cout << COLOR_WHITE;
  std::string separator(logo_width, '═');
  std::cout << pad << separator << "\n";
  
  std::cout << COLOR_SALMON;
  std::string tagline = "★ AUTONOMOUS DRIVING SYSTEM v2.0 ★";
  int tagline_padding = padding + (logo_width - tagline.length()) / 2;
  std::cout << std::string(tagline_padding > 0 ? tagline_padding : 0, ' ') << tagline << "\n";
  
  std::cout << COLOR_WHITE;
  std::string underline = "----------------------------";
  int underline_padding = padding + (logo_width - underline.length()) / 2;
  std::cout << std::string(underline_padding > 0 ? underline_padding : 0, ' ') << underline << "\n";
  
  std::cout << COLOR_RESET << "\n";
}

void TerminalBootUI::drawSystemInfo() {
  // Center content for wide screen
  int content_width = 60;
  int screen_width = 270;
  int padding = (screen_width - content_width) / 2;
  std::string pad(padding > 0 ? padding : 0, ' ');
  
  std::cout << pad << COLOR_CYAN << "[SYSTEM]" << COLOR_RESET << " Hardware Detection\n";
  std::cout << pad << "  └─ Platform: " << COLOR_GREEN << platform << COLOR_RESET << "\n";
  std::cout << pad << "  └─ Serial: " << COLOR_GREEN << serial << COLOR_RESET << "\n";
  std::cout << pad << "  └─ IMEI: " << COLOR_GREEN << imei << COLOR_RESET << "\n\n";
}

std::string TerminalBootUI::getStatusSymbol(ServiceStatus status) {
  switch (status) {
    case ServiceStatus::PENDING:  return "[ ]";
    case ServiceStatus::STARTING: return "[~]";
    case ServiceStatus::RUNNING:  return "[✓]";
    case ServiceStatus::FAILED:   return "[✗]";
  }
  return "[?]";
}

std::string TerminalBootUI::getStatusColor(ServiceStatus status) {
  switch (status) {
    case ServiceStatus::PENDING:  return COLOR_WHITE;
    case ServiceStatus::STARTING: return COLOR_YELLOW;
    case ServiceStatus::RUNNING:  return COLOR_GREEN;
    case ServiceStatus::FAILED:   return COLOR_RED;
  }
  return COLOR_WHITE;
}

void TerminalBootUI::drawServices() {
  std::cout << COLOR_CYAN << "[SERVICES]" << COLOR_RESET << " Starting core processes:\n";
  
  for (const auto& [name, info] : services) {
    std::cout << "  ├─ " << std::left << std::setw(20) << info.display_name;
    std::cout << getStatusColor(info.status) << getStatusSymbol(info.status) << COLOR_RESET;
    
    if (!info.message.empty()) {
      std::cout << " " << COLOR_DIM << info.message << COLOR_RESET;
    }
    std::cout << "\n";
  }
  std::cout << "\n";
}

void TerminalBootUI::drawProgress() {
  int bar_width = 50;
  int filled = (progress_percentage * bar_width) / 100;
  
  std::cout << COLOR_CYAN << "[PROGRESS]" << COLOR_RESET << " ";
  std::cout << COLOR_GREEN;
  
  // Draw progress bar
  for (int i = 0; i < bar_width; ++i) {
    if (i < filled) {
      std::cout << "█";
    } else {
      std::cout << "░";
    }
  }
  
  std::cout << COLOR_RESET << " " << progress_percentage << "%\n";
  std::cout << COLOR_CYAN << "[PHASE]" << COLOR_RESET << " " << current_phase << "\n\n";
}

void TerminalBootUI::drawFooter() {
  auto now = std::chrono::steady_clock::now();
  auto duration = std::chrono::duration_cast<std::chrono::seconds>(now - boot_start);
  
  std::cout << COLOR_DIM << "Boot time: " << duration.count() << "s";
  std::cout << " | CPU: 45% | Memory: 1.2GB/4GB | Temp: 42°C" << COLOR_RESET << "\n";
  std::cout << COLOR_WHITE << "═══════════════════════════════════════════════════════" << COLOR_RESET;
}

void TerminalBootUI::render() {
  std::lock_guard<std::mutex> lock(update_mutex);
  
  // Clear and redraw
  std::cout << CLEAR_SCREEN;
  drawHeader();
  drawSystemInfo();
  drawServices();
  
  // Show errors if any services failed
  if (hasErrors()) {
    drawErrors();
  } else {
    drawProgress();
  }
  
  drawFooter();
  std::cout << std::flush;
}

bool TerminalBootUI::hasErrors() {
  for (const auto& [name, info] : services) {
    if (info.status == ServiceStatus::FAILED) {
      return true;
    }
  }
  return false;
}

void TerminalBootUI::drawErrors() {
  std::cout << "\n" << COLOR_RED << STYLE_BOLD << "[ERRORS DETECTED]" << COLOR_RESET << " Boot halted due to failures:\n\n";
  
  for (const auto& [name, info] : services) {
    if (info.status == ServiceStatus::FAILED) {
      // Error header
      std::cout << COLOR_RED << "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" << COLOR_RESET << "\n";
      std::cout << COLOR_RED << STYLE_BOLD << "FAILED: " << info.display_name << COLOR_RESET << "\n";
      
      // Basic error message
      if (!info.message.empty()) {
        std::cout << COLOR_YELLOW << "Error: " << COLOR_RESET << info.message << "\n";
      }
      
      // File location
      if (!info.error_file.empty()) {
        std::cout << COLOR_CYAN << "Location: " << COLOR_RESET 
                  << info.error_file;
        if (info.error_line > 0) {
          std::cout << ":" << info.error_line;
        }
        std::cout << "\n";
      }
      
      // Detailed error/stack trace
      if (!info.error_details.empty()) {
        std::cout << COLOR_DIM << "\nStack Trace:\n" << COLOR_RESET;
        
        // Split and format stack trace for readability
        std::istringstream trace_stream(info.error_details);
        std::string line;
        int frame_num = 0;
        while (std::getline(trace_stream, line)) {
          if (line.find("File") != std::string::npos || line.find("line") != std::string::npos) {
            // Highlight file references
            std::cout << COLOR_CYAN << "  #" << frame_num++ << " " << line << COLOR_RESET << "\n";
          } else {
            std::cout << COLOR_DIM << "     " << line << COLOR_RESET << "\n";
          }
        }
      }
      
      // Actionable fix suggestions
      if (!info.suggested_fix.empty()) {
        std::cout << "\n" << COLOR_GREEN << STYLE_BOLD << "SUGGESTED FIX:" << COLOR_RESET << "\n";
        std::cout << COLOR_GREEN << info.suggested_fix << COLOR_RESET << "\n";
      }
      
      std::cout << "\n";
    }
  }
  
  // General debugging tips
  std::cout << COLOR_YELLOW << "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" << COLOR_RESET << "\n";
  std::cout << COLOR_YELLOW << STYLE_BOLD << "DEBUGGING TIPS:" << COLOR_RESET << "\n";
  std::cout << "• Check " << COLOR_CYAN << "/data/log/" << COLOR_RESET << " for detailed logs\n";
  std::cout << "• Try: " << COLOR_CYAN << "cd /data/openpilot && ./launch_openpilot.sh" << COLOR_RESET << "\n";
  std::cout << "• Common issues: permissions, missing deps, CAN errors\n";
  std::cout << "• SSH will be available after thermald starts\n";
}

void TerminalBootUI::updateService(const std::string& name, ServiceStatus status, const std::string& message) {
  std::lock_guard<std::mutex> lock(update_mutex);
  if (services.find(name) != services.end()) {
    services[name].status = status;
    services[name].message = message;
  }
}

void TerminalBootUI::setProgress(int percentage) {
  std::lock_guard<std::mutex> lock(update_mutex);
  progress_percentage = std::min(100, std::max(0, percentage));
}

void TerminalBootUI::setPhase(const std::string& phase) {
  std::lock_guard<std::mutex> lock(update_mutex);
  current_phase = phase;
}

void TerminalBootUI::update(const std::string& input) {
  // Parse input commands
  // Formats:
  //   "service:status:message"
  //   "service:error:message:file:line:details:suggested_fix"
  //   "percentage" (just digits)
  //   "phase text"
  
  if (input.find(':') != std::string::npos) {
    std::vector<std::string> parts;
    std::istringstream iss(input);
    std::string part;
    
    while (std::getline(iss, part, ':')) {
      parts.push_back(part);
    }
    
    if (parts.size() >= 2) {
      const std::string& service = parts[0];
      const std::string& status_str = parts[1];
      
      if (status_str == "error" && parts.size() >= 7) {
        // Extended error format
        if (services.find(service) != services.end()) {
          services[service].status = ServiceStatus::FAILED;
          services[service].message = parts[2];
          services[service].error_file = parts[3];
          services[service].error_line = parts[4].empty() ? 0 : std::stoi(parts[4]);
          services[service].error_details = parts[5];
          services[service].suggested_fix = parts[6];
        }
      } else {
        // Regular status update
        ServiceStatus status = ServiceStatus::PENDING;
        if (status_str == "starting") status = ServiceStatus::STARTING;
        else if (status_str == "running") status = ServiceStatus::RUNNING;
        else if (status_str == "failed") status = ServiceStatus::FAILED;
        
        std::string message = parts.size() > 2 ? parts[2] : "";
        updateService(service, status, message);
      }
    }
  } else if (std::all_of(input.begin(), input.end(), ::isdigit)) {
    // Progress update
    setProgress(std::stoi(input));
  } else {
    // Phase update
    setPhase(input);
  }
}