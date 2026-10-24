"""
Comprehensive Test Suite for Donor Availability and Request Tracking in QuickBlood
Tests:
1. Donor Availability toggle, persistence, and eligibility calculation
2. Request Status Tracking across all 6 states: Pending, Accepted, Donation in Progress, Fulfilled, Cancelled, Rejected
3. Donation Confirmation: Mark Donation as Completed & Confirm Blood Received
4. Isolation: Completing one request does not affect other requests
5. Security & Authorization: Ownership checks, role validation, duplicate action prevention
"""

import os
from datetime import datetime
import app

def run_all_tests():
    print("=" * 70)
    print("QUICKBLOOD: DONOR AVAILABILITY & REQUEST TRACKING TEST SUITE")
    print("=" * 70)

    with app.app.app_context():
        client = app.app.test_client()

        # -------------------------------------------------------------------
        # Test 1: Donor Availability Toggle & Persistence
        # -------------------------------------------------------------------
        print("\n[TEST 1] Donor Availability Toggle & Database Persistence")
        
        # Pick or create a test donor user
        test_donor = app.User.query.filter_by(role='Donor').first()
        assert test_donor is not None, "A donor user must exist"
        donor_profile = test_donor.donor_profile
        assert donor_profile is not None, "Donor profile must exist"

        # Set known initial state
        donor_profile.is_available = True
        app.db.session.commit()

        # Log in as test donor via session
        with client.session_transaction() as sess:
            sess['user_id'] = test_donor.id
            sess['user_name'] = test_donor.name
            sess['user_role'] = test_donor.role

        # Toggle to Unavailable via API
        res = client.post('/api/toggle-availability', json={'is_available': False})
        data = res.get_json()
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert data['success'] is True
        assert data['is_available'] is False
        assert data['status_text'] == 'Unavailable'

        # Verify DB persistence
        refreshed_donor = app.DonorProfile.query.get(donor_profile.id)
        assert refreshed_donor.is_available is False, "DB must persist is_available=False"
        print("  -> Toggled to Unavailable: verified in API and DB.")

        # Toggle back to Available
        res = client.post('/api/toggle-availability', json={'is_available': True})
        data = res.get_json()
        assert data['is_available'] is True
        assert data['status_text'] == 'Available'

        refreshed_donor = app.DonorProfile.query.get(donor_profile.id)
        assert refreshed_donor.is_available is True, "DB must persist is_available=True"
        print("  -> Toggled back to Available: verified in API and DB.")

        # Eligibility calculation test
        elig = refreshed_donor.eligibility
        assert 'is_eligible' in elig
        assert 'status_label' in elig
        assert 'days_remaining' in elig
        print(f"  -> Donor Eligibility calculated: {elig['status_label']} ({elig['message']})")
        print("  [PASS] Test 1 Completed Successfully.")

        # -------------------------------------------------------------------
        # Test 2: Complete Request Lifecycle (Pending -> Accepted -> In Progress -> Fulfilled)
        # -------------------------------------------------------------------
        print("\n[TEST 2] Request Lifecycle (Pending -> Accepted -> In Progress -> Fulfilled)")

        # Create a receiver user and a separate donor user
        receiver = app.User.query.filter(app.User.role.in_(['Receiver', 'Both'])).first()
        if not receiver:
            receiver = app.User(name="Test Receiver", email="receiver.test@example.com", password_hash="dummy", phone="9999999999", role="Receiver")
            app.db.session.add(receiver)
            app.db.session.commit()

        donor_user = app.User.query.filter(app.User.id != receiver.id, app.User.role.in_(['Donor', 'Both'])).first()
        assert donor_user is not None, "Need a distinct donor user"

        # 2a. Post new Blood Request (State: Pending)
        req = app.BloodRequest(
            user_id=receiver.id,
            patient_name="Anand Sharma",
            blood_group="O+",
            hospital_name="Apollo Clinic",
            city="Nashik",
            units_needed=2,
            urgency="Urgent",
            contact_phone="9876543210",
            status="Pending"
        )
        app.db.session.add(req)
        app.db.session.commit()
        req_id = req.id

        assert req.status == 'Pending'
        assert req.progress_step == 1
        assert req.status_badge_class == 'status-pending'
        print(f"  -> Request #{req_id} created in 'Pending' status (Step {req.progress_step}).")

        # 2b. Donor Accepts the Request (State: Pending -> Accepted)
        with client.session_transaction() as sess:
            sess['user_id'] = donor_user.id
            sess['user_name'] = donor_user.name
            sess['user_role'] = donor_user.role

        res = client.post(f'/requests/{req_id}/accept', follow_redirects=True)
        assert res.status_code == 200
        
        req_refreshed = app.BloodRequest.query.get(req_id)
        assert req_refreshed.status == 'Accepted', f"Status should be Accepted, got {req_refreshed.status}"
        assert req_refreshed.donor_id == donor_user.id, "Donor ID must be assigned"
        assert req_refreshed.progress_step == 2
        assert req_refreshed.status_badge_class == 'status-accepted'
        print(f"  -> Donor #{donor_user.id} accepted request #{req_id}. Status: 'Accepted' (Step {req_refreshed.progress_step}).")

        # 2c. Start Progress (State: Accepted -> Donation in Progress)
        res = client.post(f'/requests/{req_id}/start-progress', follow_redirects=True)
        assert res.status_code == 200
        req_refreshed = app.BloodRequest.query.get(req_id)
        assert req_refreshed.status == 'Donation in Progress'
        assert req_refreshed.progress_step == 3
        assert req_refreshed.status_badge_class == 'status-in-progress'
        print(f"  -> Donation procedure started. Status: 'Donation in Progress' (Step {req_refreshed.progress_step}).")

        # 2d. Donor Marks Donation as Completed (Requirement 3)
        # Record initial donor units & availability
        initial_donor_units = donor_user.donor_profile.units_donated or 0
        donor_user.donor_profile.is_available = True
        app.db.session.commit()

        res = client.post(f'/requests/{req_id}/mark-completed', follow_redirects=True)
        assert res.status_code == 200

        req_refreshed = app.BloodRequest.query.get(req_id)
        donor_profile_refreshed = app.DonorProfile.query.filter_by(user_id=donor_user.id).first()

        assert req_refreshed.donor_completed is True, "donor_completed flag must be True"
        assert donor_profile_refreshed.is_available is False, "Donor must automatically be marked Unavailable after donation"
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        assert donor_profile_refreshed.last_donated == today_str, f"Last donation date must be today's date ({today_str})"
        assert donor_profile_refreshed.units_donated == initial_donor_units + req_refreshed.units_needed, "Units donated must be incremented"

        # Verify donation record created
        donation_rec = app.DonationRecord.query.filter_by(request_id=req_id).first()
        assert donation_rec is not None, "DonationRecord must be created in donation history"
        assert donation_rec.donor_id == donor_user.id
        assert donation_rec.units == req_refreshed.units_needed
        print(f"  -> Donor marked donation completed:")
        print(f"     - is_available: {donor_profile_refreshed.is_available} (Automatically Unavailable)")
        print(f"     - last_donated: {donor_profile_refreshed.last_donated}")
        print(f"     - units_donated: {donor_profile_refreshed.units_donated}")
        print(f"     - history log created: Record #{donation_rec.id} ({donation_rec.status})")

        # 2e. Recipient Confirms Blood Received (State: -> Fulfilled)
        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id
            sess['user_name'] = receiver.name
            sess['user_role'] = receiver.role

        res = client.post(f'/requests/{req_id}/confirm-received', follow_redirects=True)
        assert res.status_code == 200

        req_refreshed = app.BloodRequest.query.get(req_id)
        assert req_refreshed.status == 'Fulfilled', f"Expected status Fulfilled, got {req_refreshed.status}"
        assert req_refreshed.progress_step == 4
        assert req_refreshed.status_badge_class == 'status-fulfilled'
        assert req_refreshed.fulfilled_at is not None

        # Verify donation history record updated
        donation_rec = app.DonationRecord.query.filter_by(request_id=req_id).first()
        assert donation_rec.status == 'Fulfilled & Received'
        print(f"  -> Recipient confirmed blood received. Status: 'Fulfilled' (Step {req_refreshed.progress_step}).")
        print("  [PASS] Test 2 Completed Successfully.")

        # -------------------------------------------------------------------
        # Test 3: Request Cancellation & Re-opening (Cancelled State)
        # -------------------------------------------------------------------
        print("\n[TEST 3] Request Cancellation & Re-open (Cancelled -> Pending)")
        
        req_cancel = app.BloodRequest(
            user_id=receiver.id,
            patient_name="Pooja Shinde",
            blood_group="A+",
            hospital_name="Nashik Civil Hospital",
            city="Nashik",
            units_needed=1,
            urgency="Normal",
            contact_phone="9876543211",
            status="Pending"
        )
        app.db.session.add(req_cancel)
        app.db.session.commit()
        cancel_id = req_cancel.id

        # Cancel request as receiver
        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id
        res = client.post(f'/requests/{cancel_id}/cancel', follow_redirects=True)
        assert res.status_code == 200

        req_cancel_refreshed = app.BloodRequest.query.get(cancel_id)
        assert req_cancel_refreshed.status == 'Cancelled'
        assert req_cancel_refreshed.status_badge_class == 'status-cancelled'
        assert req_cancel_refreshed.cancelled_at is not None
        print(f"  -> Request #{cancel_id} cancelled successfully.")

        # Reopen request
        res = client.post(f'/requests/{cancel_id}/reopen', follow_redirects=True)
        assert res.status_code == 200
        req_cancel_refreshed = app.BloodRequest.query.get(cancel_id)
        assert req_cancel_refreshed.status == 'Pending'
        print(f"  -> Request #{cancel_id} reopened to 'Pending'.")
        print("  [PASS] Test 3 Completed Successfully.")

        # -------------------------------------------------------------------
        # Test 4: Request Rejection State
        # -------------------------------------------------------------------
        print("\n[TEST 4] Request Rejection (Rejected State)")
        
        req_reject = app.BloodRequest(
            user_id=receiver.id,
            patient_name="Rahul Verma",
            blood_group="B+",
            hospital_name="Six Sigma Hospital",
            city="Nashik",
            units_needed=1,
            urgency="Normal",
            contact_phone="9876543212",
            status="Pending"
        )
        app.db.session.add(req_reject)
        app.db.session.commit()
        reject_id = req_reject.id

        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id
        res = client.post(f'/requests/{reject_id}/reject', data={'reason': 'No longer required by physician', 'action_type': 'reject_request'}, follow_redirects=True)
        assert res.status_code == 200

        req_reject_refreshed = app.BloodRequest.query.get(reject_id)
        assert req_reject_refreshed.status == 'Rejected'
        assert req_reject_refreshed.status_badge_class == 'status-rejected'
        assert req_reject_refreshed.rejection_reason == 'No longer required by physician'
        print(f"  -> Request #{reject_id} marked as 'Rejected' with reason logged.")
        print("  [PASS] Test 4 Completed Successfully.")

        # -------------------------------------------------------------------
        # Test 5: Isolation & Non-Interference
        # -------------------------------------------------------------------
        print("\n[TEST 5] Isolation Check (Completing Req A does not alter Req B)")
        
        req_a = app.BloodRequest(
            user_id=receiver.id,
            patient_name="Patient Alpha",
            blood_group="AB+",
            hospital_name="Hospital A",
            city="Nashik",
            units_needed=1,
            contact_phone="9876500001",
            status="Pending"
        )
        req_b = app.BloodRequest(
            user_id=receiver.id,
            patient_name="Patient Beta",
            blood_group="O-",
            hospital_name="Hospital B",
            city="Nashik",
            units_needed=2,
            contact_phone="9876500002",
            status="Pending"
        )
        app.db.session.add_all([req_a, req_b])
        app.db.session.commit()
        id_a, id_b = req_a.id, req_b.id

        # Accept & fulfill Req A
        with client.session_transaction() as sess:
            sess['user_id'] = donor_user.id
        client.post(f'/requests/{id_a}/accept')
        client.post(f'/requests/{id_a}/mark-completed')

        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id
        client.post(f'/requests/{id_a}/confirm-received')

        # Check that Req B remains untouched
        refreshed_b = app.BloodRequest.query.get(id_b)
        assert refreshed_b.status == 'Pending', f"Req B status must remain Pending, was {refreshed_b.status}"
        assert refreshed_b.donor_id is None, "Req B donor_id must remain None"
        assert refreshed_b.donor_completed is False, "Req B donor_completed must remain False"
        print(f"  -> Request #{id_a} fulfilled; Request #{id_b} correctly preserved in 'Pending' state.")
        print("  [PASS] Test 5 Completed Successfully.")

        # -------------------------------------------------------------------
        # Test 6: Security, Role Validation & Duplicate Action Prevention
        # -------------------------------------------------------------------
        print("\n[TEST 6] Security, Authorization & Duplicate Action Prevention")

        # 6a. Prevent user from accepting their own request
        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id  # Owner of req_b
        res = client.post(f'/requests/{id_b}/accept', follow_redirects=True)
        assert app.BloodRequest.query.get(id_b).donor_id != receiver.id, "Cannot accept own request"
        print("  -> Security: Requester prevented from accepting own request.")

        # 6b. Unauthorized user cannot mark donation completed
        unauthorized_user = app.User.query.filter(app.User.id != donor_user.id, app.User.id != receiver.id).first()
        if unauthorized_user:
            with client.session_transaction() as sess:
                sess['user_id'] = unauthorized_user.id
            res = client.post(f'/requests/{id_a}/mark-completed', json={})
            assert res.status_code == 403 or b'Only the assigned donor' in res.data, "Must reject unauthorized completion"
            print("  -> Security: Unauthorized user rejected when trying to complete donation.")

        # 6c. Prevent duplicate confirmation on already fulfilled request
        with client.session_transaction() as sess:
            sess['user_id'] = receiver.id
        res = client.post(f'/requests/{id_a}/confirm-received', json={})
        data = res.get_json()
        assert res.status_code == 400 or (data and not data.get('success')), "Must reject duplicate fulfillment"
        print("  -> Duplicate Prevention: Duplicate fulfillment cleanly prevented.")

        # 6d. Cannot cancel already fulfilled request
        res = client.post(f'/requests/{id_a}/cancel', follow_redirects=True)
        assert app.BloodRequest.query.get(id_a).status == 'Fulfilled', "Cannot cancel fulfilled request"
        print("  -> State Invariant: Fulfilled request cannot be cancelled.")
        print("  [PASS] Test 6 Completed Successfully.")

    print("\n" + "=" * 70)
    print("ALL 6 TESTS PASSED! 100% VERIFICATION SUCCESSFUL.")
    print("=" * 70)

if __name__ == '__main__':
    run_all_tests()
