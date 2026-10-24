import os
import app

output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_results.txt')
print(f"Writing test output to: {output_file}")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=== QUICKBLOOD VERIFICATION SUITE ===\n")
    
    with app.app.app_context():
        # 1. Database & Models
        users_count = app.User.query.count()
        donors_count = app.DonorProfile.query.count()
        requests_count = app.BloodRequest.query.count()
        donations_count = app.DonationRecord.query.count()
        f.write(f"Total Users: {users_count}\n")
        f.write(f"Total Donors: {donors_count}\n")
        f.write(f"Total Requests: {requests_count}\n")
        f.write(f"Total Donation Records: {donations_count}\n\n")

        # 2. HTTP Routes Test
        client = app.app.test_client()

        res = client.get('/')
        assert res.status_code == 200
        f.write("[PASS] GET / (Home Page)\n")

        res = client.get('/donors?blood_group=O-&available_only=1')
        assert res.status_code == 200
        f.write("[PASS] GET /donors (Donor Search Page)\n")

        res = client.get('/api/donors?blood_group=O-')
        data = res.get_json()
        assert res.status_code == 200 and data['success']
        f.write(f"[PASS] GET /api/donors - Found {data['count']} matching donor(s)\n")

        res = client.get('/requests')
        assert res.status_code == 200
        f.write("[PASS] GET /requests (Emergency Requests Feed)\n")

        f.write("\nALL TESTS COMPLETED SUCCESSFULLY WITH 100% PASS RATE!\n")

print("Test suite execution complete!")
