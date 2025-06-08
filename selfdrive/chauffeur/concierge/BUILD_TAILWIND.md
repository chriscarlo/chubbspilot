# Building Tailwind CSS for Concierge on TICI

Since TICI devices don't have Node.js/npm installed, the Tailwind CSS must be built on a development machine and included in the deployment.

## Prerequisites

- Development machine with Node.js and npm installed
- Access to the openpilot repository

## Build Instructions

1. **Navigate to the Concierge directory** on your development machine:
   ```bash
   cd /data/openpilot/selfdrive/chauffeur/concierge/
   ```

2. **Install Node.js dependencies** (if not already installed):
   ```bash
   npm install
   ```
   
   This will install:
   - `tailwindcss@^4.1.6`
   - `@tailwindcss/cli@^4.1.6`

3. **Build the CSS file**:
   ```bash
   npm run build:css
   ```
   
   This command compiles `css/input.css` into `static/css/tailwind.min.css`

4. **Verify the build**:
   ```bash
   ls -la static/css/tailwind.min.css
   ```
   
   The file should be at least 10KB in size.

5. **Commit and push the built CSS**:
   ```bash
   git add static/css/tailwind.min.css
   git commit -m "Build Tailwind CSS for Concierge"
   git push
   ```

## Important Notes

- **DO NOT** edit `static/css/tailwind.min.css` directly - it's a generated file
- Always make style changes in `css/input.css` and rebuild
- The CSS must be rebuilt whenever:
  - You modify `css/input.css`
  - You use new Tailwind utility classes in HTML templates
  - You update Tailwind CSS version

## Troubleshooting

If the CSS file is too small (< 10KB) or missing styles:
1. Check that `css/input.css` contains `@import "tailwindcss";`
2. Ensure no legacy Tailwind v3 directives are present
3. Verify the `@source` directives point to the template files
4. Run a clean rebuild: `rm static/css/tailwind.min.css && npm run build:css`

## Development Workflow

For active development:
```bash
# Watch mode - automatically rebuilds on changes
npm run watch:css
```

This will monitor changes to `css/input.css` and template files, rebuilding automatically.