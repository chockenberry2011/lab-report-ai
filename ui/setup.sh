#!/bin/bash

# Lab AI UI Setup Script

set -e

echo "🚀 Setting up Lab AI React UI..."

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

# Check Node version
NODE_VERSION=$(node --version | cut -d. -f1 | sed 's/v//')
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 18+ is required. Current version: $(node --version)"
    exit 1
fi

echo "✅ Node.js $(node --version) detected"

# Install dependencies
echo "📦 Installing dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

# Create environment file if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local file..."
    cat > .env.local << EOL
# Lab AI UI Environment Variables
VITE_API_URL=http://localhost:8000
EOL
    echo "✅ Created .env.local with default settings"
else
    echo "✅ .env.local already exists"
fi

# Run type check
echo "🔍 Running TypeScript check..."
npx tsc --noEmit

# Run linting
echo "🧹 Running ESLint..."
npm run lint

# Create directories
echo "📁 Creating necessary directories..."
mkdir -p public
mkdir -p src/assets

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Available commands:"
echo "  npm run dev     - Start development server"
echo "  npm run build   - Build for production"
echo "  npm run preview - Preview production build"
echo "  npm run lint    - Run ESLint"
echo ""
echo "🌐 The UI will be available at:"
echo "  Development: http://localhost:3000"
echo "  Production:  http://localhost:3000 (when using Docker)"
echo ""
echo "🔧 Make sure the Lab AI API is running at http://localhost:8000"
echo "   Start the full system with: docker-compose up"
echo ""

# Optionally start dev server
read -p "🚀 Start development server now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting development server..."
    npm run dev
fi