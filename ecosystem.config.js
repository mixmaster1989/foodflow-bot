module.exports = {
    apps: [
        {
            name: 'foodflow-bot',
            script: 'main.py',
            interpreter: '/home/user1/foodflow-bot/venv/bin/python',
            cwd: '/home/user1/foodflow-bot',
            instances: 1,
            autorestart: true,
            watch: false,
            max_memory_restart: '200M',
            env: {
                NODE_ENV: 'production'
            },
            log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
            merge_logs: true,
            time: true
        }
    ]
};
