module.exports = {
  apps: [
    {
      name: "biblio-backend",
      script: "./.venv/bin/uvicorn",
      args: "src.api.main:app --host 0.0.0.0 --port 8005",
      interpreter: "none", // Do not use PM2's default interpreters
      autorestart: true,
      watch: ["src"],
      ignore_watch: ["node_modules", "pipeline_results", "data", "__pycache__"],
      env: {
        PYTHONPATH: ".",
        OPENALEX_EMAIL: "your-email@example.com"
      }
    },
    {
      name: "biblio-frontend",
      cwd: "./frontend",
      script: "npm",
      args: "run dev -- -p 3005",
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: "development",
        NEXT_PUBLIC_API_URL: "https://johngf.xyz/biblio-api"
      }
    }
  ]
};
