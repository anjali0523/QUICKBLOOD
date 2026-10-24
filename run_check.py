import app

def test():
    print("=== QUICKBLOOD NASHIK REGION VERIFICATION ===")
    
    with app.app.app_context():
        users = app.User.query.all()
        donors = app.DonorProfile.query.all()
        requests = app.BloodRequest.query.all()
        nashik_donors = app.DonorProfile.query.filter(app.DonorProfile.city.ilike('%Nashik%')).all()
        
        print(f"Total Registered Users: {len(users)}")
        print(f"Total Donors: {len(donors)}")
        print(f"Nashik Region Donors: {len(nashik_donors)}")
        print(f"Active Hospital Requests: {len(requests)}")

        print("\n--- Nashik Donors Directory Preview ---")
        for d in nashik_donors:
            status = "Available" if d.is_available else "Unavailable"
            print(f"Donor: {d.user.name} | Blood Group: {d.blood_group} | City: {d.city} | Status: {status} | Phone: {d.user.phone}")

        print("\n--- Emergency Requests in Nashik Hospitals ---")
        for r in requests:
            print(f"Patient: {r.patient_name} ({r.blood_group}) at {r.hospital_name}, {r.city} | Phone: {r.contact_phone}")

        # Flask Test Client Route Verification
        client = app.app.test_client()
        
        # Donors search route for Nashik
        res_donors = client.get('/donors?blood_group=A+&city=Nashik&available_only=1')
        assert res_donors.status_code == 200
        print("\n[OK] Route '/donors?blood_group=A+&city=Nashik' executed successfully")

        # API Route JSON check for Nashik
        res_api = client.get('/api/donors?city=Nashik')
        json_data = res_api.get_json()
        assert res_api.status_code == 200 and json_data['success']
        print(f"[OK] Route '/api/donors?city=Nashik' returned {json_data['count']} matching Nashik donor(s)")

        print("\n>>> ALL NASHIK DATA VERIFICATION CHECKS PASSED PERFECTLY! <<<")

if __name__ == '__main__':
    test()
