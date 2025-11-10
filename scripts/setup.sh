```bash
#!/bin/bash

echo "Setting up Code Review Assistant..."
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p data/raw data/processed data/vector_db logs

# Copy environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please update with your API keys."
fi

echo "Setup complete!"
echo "Next steps:"
echo "1. Update .env with your API keys"
echo "2. Run: python scripts/ingest_reviews.py --repo owner/repo"
echo "3. Start API: uvicorn src.api.app:app --reload"
```