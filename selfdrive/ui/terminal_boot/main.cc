#include <iostream>
#include <thread>
#include <csignal>
#include "selfdrive/ui/terminal_boot/terminal_ui.h"

volatile sig_atomic_t running = 1;
volatile sig_atomic_t needs_redraw = 0;

void signal_handler(int signal) {
  running = 0;
}

void winch_handler(int signal) {
  needs_redraw = 1;
}

int main(int argc, char* argv[]) {
  // Set up signal handlers
  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);
  signal(SIGWINCH, winch_handler);  // Terminal resize
  
  // Initialize terminal UI
  TerminalBootUI ui;
  ui.init();
  
  // Initial render
  ui.render();
  
  // Read input from stdin (like the original spinner)
  std::string line;
  while (running && std::getline(std::cin, line)) {
    if (!line.empty()) {
      ui.update(line);
      ui.render();
    }
    
    // Check for terminal resize
    if (needs_redraw) {
      needs_redraw = 0;
      ui.render();
    }
  }
  
  return 0;
}