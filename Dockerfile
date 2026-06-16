# ── PricePulse – Production Dockerfile ─────────────────────────────
FROM python:3.11-slim

LABEL maintainer="PricePulse"
LABEL description="Grocery Price Comparator – Zepto · Blinkit · Instamart · BigBasket"

# ── System deps ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────
WORKDIR /app

# ── Python deps (cached layer) ───────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────
COPY . .

# ── Create data directory with correct permissions ─────────────
RUN mkdir -p /app/database && chmod 755 /app/database

# ── Expose Streamlit port ────────────────────────────────────────
EXPOSE 8501

# ── Health check ─────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Run ──────────────────────────────────────────────────────────
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
