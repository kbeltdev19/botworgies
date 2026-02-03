import sqlite3
import random
from datetime import datetime, timedelta

class PlatformBalancer:
    def __init__(self, db_name='platform_balancer.db'):
        self.db_name = db_name
        self.platforms = {
            'linkedin': {'quota': 50, 'jobs': [], 'applications_today': 0, 'success_rate': 0.0},
            'greenhouse': {'quota': 500, 'jobs': [], 'applications_today': 0, 'success_rate': 0.0},
            'lever': {'quota': 200, 'jobs': [], 'applications_today': 0, 'success_rate': 0.0},
            'direct': {'quota': 250, 'jobs': [], 'applications_today': 0, 'success_rate': 0.0}
        }
        self.weights = {'linkedin': 1.0, 'greenhouse': 1.0, 'lever': 1.0, 'direct': 1.0}
        self.applications_today = 0
        self._setup_db()

    def _setup_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS platforms (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                quota INTEGER NOT NULL,
                jobs TEXT NOT NULL,
                applications_today INTEGER NOT NULL,
                success_rate REAL NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                platform_name TEXT NOT NULL,
                job_id TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def reset_quotas(self):
        for platform, data in self.platforms.items():
            data['quota'] = self.platforms[platform]['quota']
            data['applications_today'] = 0
        self.applications_today = 0
        self._update_db()

    def _update_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        for platform, data in self.platforms.items():
            cursor.execute('''
                INSERT OR REPLACE INTO platforms (id, name, quota, jobs, applications_today, success_rate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (platforms[platform]['id'], platform, data['quota'], str(data['jobs']), data['applications_today'], data['success_rate']))
        conn.commit()
        conn.close()

    def _get_platform_id(self, platform_name):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM platforms WHERE name = ?', (platform_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_next_platform(self):
        platforms = [platform for platform, data in self.platforms.items() if data['quota'] > 0]
        if not platforms:
            return None
        weighted_platforms = []
        for platform in platforms:
            weight = self.weights[platform]
            for _ in range(int(weight * 100)):
                weighted_platforms.append(platform)
        return random.choice(weighted_platforms)

    def get_next_job(self, platform):
        if platform not in self.platforms or not self.platforms[platform]['jobs']:
            return None
        job = self.platforms[platform]['jobs'].pop(0)
        return job

    def track_application(self, platform, job_id):
        if platform not in self.platforms:
            return
        self.platforms[platform]['quota'] -= 1
        self.platforms[platform]['applications_today'] += 1
        self.applications_today += 1
        if self.platforms[platform]['quota'] < int(self.platforms[platform]['quota'] * 0.1):
            self.weights[platform] *= 0.9
        self._update_db()
        return True

    def add_job(self, platform, job_id):
        if platform not in self.platforms:
            return False
        self.platforms[platform]['jobs'].append(job_id)
        return True

    def update_success_rate(self, platform, success):
        if platform not in self.platforms:
            return False
        self.platforms[platform]['success_rate'] = (self.platforms[platform]['success_rate'] * (self.platforms[platform]['applications_today'] - 1) + success) / self.platforms[platform]['applications_today']
        return True

# Example usage:
if __name__ == '__main__':
    balancer = PlatformBalancer()
    balancer.add_job('linkedin', 'job1')
    balancer.add_job('greenhouse', 'job2')
    balancer.add_job('lever', 'job3')
    balancer.add_job('direct', 'job4')

    platform =