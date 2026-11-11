Siap bro. Berarti untuk Day 1, saya yang menyusun dan menyelesaikan seluruh pekerjaan desainnya, bukan memberikan daftar tugas yang harus kamu isi.

Saya akan mengambil keputusan desain berdasarkan konsep LaFriend yang sudah kita sepakati, termasuk Session-First Matching, Partner Matching sebagai fallback, group feasibility, dan explainable rule-based engine.

Di bawah ini saya susun hasil pekerjaan Day 1 sebagai dokumen spesifikasi awal. Keputusan yang belum mempunyai hasil pengujian saya tandai sebagai baseline/asumsi desain, bukan seolah-olah sudah terbukti optimal.
DAY 1 — LaFriend System Concept & Business Rules Specification
Day 1 deliverable
Disusun

LaFriend — System Concept & Business Rules

Dokumen desain sistem · Version 1.0 · 11 November 2026

7
Entitas utama

25
Aturan bisnis awal

2
Jalur matching

3
Lifecycle utama

LaFriend — System Concept & Business Rules Specification
Document: Day 1 — System Concept and Business Rules
Version: 1.0
Date: 11 November 2026
Status: Initial Design Baseline
Product: LaFriend

1. Product Definition
   1.1 Product Overview
   LaFriend is a need-driven study partner discovery and group formation platform designed to help university students transform their individual learning needs into feasible collaborative study sessions.

Unlike conventional student discovery platforms that primarily rely on profiles or social connections, LaFriend starts with a specific learning need, evaluates academic and scheduling compatibility, and prioritizes existing study sessions before introducing new potential study partners.
1.2 Core Product Objective
The primary objective of LaFriend is to reduce the time and uncertainty involved in finding suitable study partners and organizing collaborative learning sessions.

The system does not consider the number of recommendations or matches as its ultimate measure of success. Its primary outcome is the creation of confirmed and successfully conducted study sessions.
1.3 Core Product Principles
Principle 1 — Need-Driven Matching

Matching begins with a student's specific learning requirement, represented by a Study Intent, rather than relying exclusively on student profiles.

Principle 2 — Session-First Matching

The system prioritizes existing feasible Study Sessions before searching for individual students with compatible Study Intents.

Principle 3 — Constraint-First Evaluation

Candidates must satisfy mandatory feasibility requirements before receiving compatibility scores.

Principle 4 — Explainable Recommendations

Every recommendation should provide understandable reasons for its relevance, including shared learning topics, compatible goals, and overlapping schedules.

Principle 5 — Outcome-Oriented Evaluation

The system evaluates its performance through confirmed sessions, completed sessions, time to confirmation, and participant feedback.

2. System Scope
   2.1 Target Users
   The initial target users are first- and second-year Telkom University students who need assistance finding suitable study partners for specific courses or learning topics.

The initial pilot may focus on one first-year course to simplify implementation and adoption validation.
2.2 Supported Activities
LaFriend supports the following primary activities:

1. Student registration and campus verification.
2. Student profile management.
3. Study Intent creation and management.
4. Existing Study Session discovery.
5. Study Intent compatibility evaluation.
6. Partner recommendations.
7. Group feasibility validation.
8. Joining requests and invitations.
9. Session scheduling and confirmation.
10. Session feedback and system evaluation.
    2.3 Out-of-Scope Activities for Version 1
    The initial system will not implement:

- AI-based compatibility ranking.
- Automatic group optimization across large populations.
- Autonomous schedule negotiation without participant approval.
- Real-time dynamic weight adjustment.
- Academic performance prediction.
- Full learning management system functionality.
- Automatic generation of course materials or study content.
  The matching engine will use an explainable rule-based approach. GLiNER may optionally assist with course and topic extraction from free-text input, but it will not determine compatibility rankings.

3. Actor Definition
   LaFriend has three user roles based on activities and one system-level actor.
   3.1 Student
   A Student is a verified university user who can create Study Intents, receive recommendations, join sessions, invite other students, and submit feedback.
   3.2 Session Host
   A Session Host is a student responsible for creating or managing a Study Session.

Responsibilities:

- Define session requirements.
- Publish available session slots.
- Review joining requests.
- Invite potential participants.
- Propose the final session schedule.
- Manage session membership.
- Confirm or cancel a session according to system rules.
  A Session Host is not a separate account type. Any Student may act as a host.
  3.3 Session Member
  A Session Member is a student who participates in an existing or newly formed Study Session.

Responsibilities:

- Review session information.
- Accept or reject invitations.
- Request to join an existing session.
- Confirm proposed schedules.
- Participate in the study session.
- Submit feedback.
  3.4 LaFriend System
  The LaFriend System is responsible for:
- Input validation and normalization.
- Study Intent management.
- Hard constraint filtering.
- Compatibility scoring.
- Session and partner ranking.
- Group feasibility evaluation.
- Session lifecycle management.
- Feedback collection.
- System performance evaluation.
  A separate moderator or administrator role may manage reports and account safety, but it is not part of the core matching workflow.

4. Core Entity Definitions
   The system is organized around seven primary entities.
   4.1 Student Profile
   Represents a student's identity and relatively persistent academic information.

Examples of information:

- Student ID.
- Name.
- University email.
- Study program.
- Academic year.
- Enrolled courses.
- Account verification status.
  4.2 Study Intent
  Represents one student's specific learning need.

A Study Intent is the primary input to the LaFriend matching process.

Example:

A student wants to study Binary Trees and Graphs for an upcoming midterm examination and is available on Friday morning.

One student may own multiple active Study Intents for different courses or materially different learning needs.
4.3 Study Session
Represents an actual collaborative learning activity.

A Study Session contains:

- Course.
- Learning topics.
- Learning objectives.
- Collaboration preferences.
- Available or proposed schedule slots.
- Learning mode.
- Host.
- Participant capacity.
- Session status.
  A Study Session is different from a Study Intent. An intent represents an individual requirement, while a session represents a concrete activity involving multiple students.
  4.4 Match Result
  Stores the results of the matching process.

A Match Result should identify:

- The source Study Intent.
- The recommended candidate.
- Candidate type: existing session or potential partner.
- Hard constraint results.
- Compatibility score.
- Individual scoring components.
- Recommendation explanation.
- Recommendation timestamp.
  4.5 Invitation / Join Request
  Represents a request or invitation to participate in a Study Session or newly forming group.

It records the initiator, recipient, related Study Session, status, and timestamps.
4.6 Session Membership
Represents the relationship between a student and a Study Session.

It records the participant's role and membership status.

The host is also counted as a session participant.
4.7 Feedback
Represents the evaluation submitted after a recommendation or study session.

Feedback is associated with the relevant student, Study Session, recommendation, and evaluation category.

5. Core Business Rules
   5.1 Student and Account Rules
   BR-01 — Verified Access

Only students with successfully verified university accounts may create Study Intents or participate in sessions.

BR-02 — Flexible User Roles

One student may act as a Session Host in one session and a Session Member in another.

BR-03 — Account Safety

Blocked or restricted accounts cannot participate in new matching recommendations until their account status permits participation.

BR-04 — Privacy

Personal information displayed during discovery must be limited to information necessary for assessing academic compatibility and participation.

5.2 Study Intent Rules
BR-05 — Multiple Active Intents

A student may maintain multiple active Study Intents for different learning needs.

BR-06 — Duplicate Prevention

The system should prevent identical active Study Intents from being created repeatedly by the same student.

An initial duplicate definition is based on the same student, course, normalized topic set, learning goal, and overlapping validity period.

BR-07 — Required Learning Information

Each Study Intent must identify its course, learning topics or scope, learning goal, target date window, availability, and group size preference.

BR-08 — Date Window

A Study Intent must define an acceptable session date window.

The window contains an earliest acceptable date and a latest acceptable date. An optional preferred date may indicate the student's ideal date.

BR-09 — Intent Expiration

A Study Intent remains active until it is fulfilled, cancelled by its owner, or reaches its latest acceptable date without a confirmed session.

BR-10 — Single Active Fulfillment Process

A Study Intent may have multiple recommendations, but only one active fulfillment process at a time.

The student must withdraw or resolve an outstanding join request or group formation process before pursuing another fulfillment path for the same intent.

5.3 Matching Rules
BR-11 — Session-First Priority

The system must search eligible existing Study Sessions before performing Partner Matching.

BR-12 — Session Recommendation Threshold

Only existing sessions that satisfy hard constraints and the configured recommendation threshold are considered qualified session recommendations.

The exact numerical threshold will be determined during formula design and validation.

BR-13 — Partner Matching Fallback

Partner Matching is executed when no existing Study Session qualifies for the requesting student's Study Intent.

BR-14 — Hard Constraint Requirement

A candidate must satisfy all applicable hard constraints before receiving a compatibility score.

BR-15 — Explainable Recommendation

Every displayed recommendation must include its relevant compatibility factors. The system must not present a score without explaining its main contributing factors.

BR-16 — No Forced Matching

The system must not automatically place students into a session or group based only on compatibility scores.

Students retain control over joining, accepting invitations, and confirming participation.

5.4 Session and Group Formation Rules
BR-17 — Explicit Host

Each Study Session must have exactly one designated host responsible for session management.

BR-18 — Host Counts as Member

The Session Host is included when calculating group capacity and minimum participant requirements.

BR-19 — Initial Group Size

The initial PoC uses a group size of 2–4 students, including the host. This is an experimental configuration and may be revised based on pilot findings.

BR-20 — Group Feasibility

A proposed group must be evaluated using the compatibility and feasibility of the entire group, not merely the compatibility between the intent owner and each individual candidate.

BR-21 — Common Schedule

All confirmed participants must have an agreed session time that is feasible for every member.

BR-22 — Mutual Approval

A newly formed group must obtain participant acceptance before a Study Session can be confirmed.

BR-23 — Final Schedule Approval

The host proposes the final schedule, and every confirmed participant must approve it.

BR-24 — Capacity Control

A participant cannot join a session if doing so would exceed its maximum capacity.

BR-25 — Session Outcome

A Study Session is considered completed only after its scheduled period has passed and its outcome has been recorded through the defined completion process.

6. Study Intent Specification
   A Study Intent represents an individual learning requirement.

Its conceptual structure is:

StudyIntent = (Course, Topics, Goal, DateWindow, Availability, Style, Mode, GroupSize)
6.1 Course
The course must be selected from a standardized course catalog.

Course identity is based on its canonical course identifier. Different text representations of the same course must resolve to the same canonical identifier.

Course matching is mandatory.
6.2 Learning Topics
Topics represent the specific learning materials the student wants to discuss or study.

Topics may be entered using standardized selections or normalized free-text input.

Topic similarity is a soft compatibility factor.
6.3 Learning Goal
Learning goals describe what the student expects to achieve during the session.

Initial categories:

- Examination preparation.
- Concept understanding.
- Problem-solving practice.
- Assignment discussion.
- Peer teaching.
  Learning goal compatibility is a soft constraint.
  6.4 Date Window
  The Study Intent uses:
- Earliest acceptable date.
- Preferred date, when applicable.
- Latest acceptable date.
  A candidate session must fall within the acceptable date window.

The preferred date influences compatibility ranking but does not override date feasibility.
6.5 Availability
Students may define multiple available time intervals.

An interval must contain a date or recurrence reference, start time, and end time.

The initial system timezone is Asia/Jakarta.
6.6 Collaboration Style
Initial categories:

- Discussion-based learning.
- Collaborative problem solving.
- Peer teaching.
- Focused independent study.
  Collaboration style is a soft compatibility factor.
  6.7 Learning Mode
  Initial options:
- Online.
- Offline.
- Flexible.
  Mode compatibility depends on the selected preferences. An exclusive mode mismatch makes a candidate ineligible, while a flexible preference may accommodate multiple modes.
  6.8 Group Size
  A student defines a desired minimum and maximum group size.

The initial PoC uses a maximum of four participants, including the host.

7. Matching Strategy
   LaFriend uses two separate matching paths.
   7.1 Path A — Session-First Matching
   The system searches for existing Study Sessions that can accommodate the requesting student.

Processing sequence:

1. Receive the Study Intent.
2. Retrieve active and joinable Study Sessions.
3. Filter sessions by course.
4. Validate date compatibility.
5. Validate schedule feasibility.
6. Validate participant capacity.
7. Validate account and safety requirements.
8. Evaluate academic and preference compatibility.
9. Rank eligible sessions.
10. Display qualified session recommendations.
    A user may submit a joining request to a selected session.

The host reviews the request and can accept or reject it.

If accepted, the proposed participant must still satisfy the session's membership and schedule rules.
7.2 Path B — Partner Matching
Partner Matching is used when no existing session meets the recommendation requirements.

Processing sequence:

1. Retrieve other students' active Study Intents.
2. Exclude the requesting student's own intents.
3. Filter by canonical course identity.
4. Validate date and schedule compatibility.
5. Validate account and safety requirements.
6. Check group size feasibility.
7. Calculate pairwise compatibility.
8. Rank eligible partner candidates.
9. Display recommendations.
10. Allow the intent owner to invite selected candidates.
    7.3 Group Formation
    When candidates mutually accept participation:
11. The initiating student becomes the provisional host of the new group, unless the participants agree to assign another host.
12. The system evaluates all members together.
13. The system checks common availability and group size constraints.
14. The host proposes an actual session slot.
15. All proposed participants approve the final slot.
16. The system creates or confirms the Study Session.
17. Related Study Intents are marked as fulfilled.
    The system must not treat a high pairwise score as sufficient evidence that an entire group is feasible.
    7.4 No-Match Handling
    If neither Session Matching nor Partner Matching finds a qualified candidate:

- The Study Intent remains active.
- The system communicates that no suitable match is currently available.
- The student may update or cancel the Study Intent.
- The system may search again when relevant new sessions or Study Intents become available.
- The intent expires when its latest acceptable date passes.
  The system must not generate an artificial recommendation merely to avoid returning an empty result.

8. Lifecycle Definitions
   8.1 Study Intent Lifecycle
   Initial conceptual states:
   State Definition
   DRAFT Intent is being created or edited.
   ACTIVE Intent is available for matching.
   JOIN_PENDING A join request for an existing session is awaiting a decision.
   GROUP_FORMING Partner candidates have accepted and group formation is in progress.
   CONVERTED The intent has successfully resulted in a confirmed Study Session.
   CANCELLED The owner has cancelled the intent.
   EXPIRED The latest acceptable date has passed without fulfillment.Transitions:

- DRAFT → ACTIVE
- ACTIVE → JOIN_PENDING
- JOIN_PENDING → CONVERTED
- JOIN_PENDING → ACTIVE
- ACTIVE → GROUP_FORMING
- GROUP_FORMING → CONVERTED
- GROUP_FORMING → ACTIVE
- ACTIVE → CANCELLED
- ACTIVE → EXPIRED
  If a fulfillment attempt fails, the intent may return to ACTIVE as long as its date window remains valid.
  8.2 Study Session Lifecycle
  Initial conceptual states:
  State Definition
  DRAFT The host is preparing a session.
  OPEN The session is published and can receive eligible participants.
  CONFIRMATION_PENDING The host has proposed a final slot and is awaiting participant approval.
  CONFIRMED The participant roster and session schedule are finalized.
  COMPLETED The session has taken place and its outcome has been recorded.
  CANCELLED The host or permitted system process has cancelled the session.
  EXPIRED The session has passed its valid scheduling window without confirmation.A FULL display condition is derived from current membership and capacity. It is not necessarily a permanent lifecycle state.

Once a session is confirmed, its participant roster is considered finalized for the initial PoC.
8.3 Membership Lifecycle
Initial membership states:
State Definition
REQUESTED A student has requested to join.
INVITED A student has received an invitation.
ACCEPTED The student has accepted participation.
DECLINED The student has rejected the request or invitation.
WITHDRAWN The student has withdrawn before session confirmation.
CONFIRMED The student is included in the finalized session roster. 9. Feedback and Evaluation Principles
Feedback is separated into three categories.
9.1 Recommendation Feedback
Collected when a student interacts with a recommendation.

Information may include:

- Topic relevance.
- Schedule suitability.
- Goal compatibility.
- Join, ignore, or reject decisions.
  9.2 Session Feedback
  Collected after a session's scheduled period.

Information may include:

- Whether the session took place.
- Topic relevance.
- Schedule suitability.
- Collaboration suitability.
- Perceived usefulness.
  Feedback is submitted individually by participants.
  9.3 Operational Feedback
  Collected automatically by the system.

Information includes:

- Study Intent creation time.
- Recommendation generation time.
- Join request time.
- Invitation response time.
- Session confirmation time.
- Session status.
- Completion and cancellation timestamps.
  9.4 Feedback Governance
  Feedback is used for system evaluation and controlled formula calibration.

A single rating must not automatically change matching weights.

Safety reports and blocking actions are handled separately from compatibility scoring.

The initial evaluation model prioritizes:

1. Time to Session Confirmation.
2. Match-to-Session Conversion Rate.
3. Session Completion Rate.
4. Average Session Relevance.
   Exact mathematical formulas and calibration procedures will be finalized in the dedicated evaluation-design phase.

5. User Flow Definitions
   Flow A — Joining an Existing Study Session
6. Student signs in.
7. Student creates a Study Intent.
8. System validates and normalizes the input.
9. System searches existing sessions.
10. System applies hard constraints.
11. System calculates compatibility scores.
12. System displays qualified recommendations.
13. Student selects a Study Session.
14. Student requests to join.
15. Host reviews the request.
16. Host accepts or rejects.
17. If accepted, the participant is added subject to capacity and schedule rules.
18. Host proposes the final schedule.
19. Participants approve the schedule.
20. The session becomes confirmed.
21. The Study Intent is marked as converted.
    Flow B — Finding Study Partners
22. Student signs in.
23. Student creates a Study Intent.
24. System searches existing sessions.
25. No qualified session is found.
26. System searches other active Study Intents.
27. System filters ineligible candidates.
28. System calculates compatibility.
29. System displays partner recommendations.
30. Student invites selected candidates.
31. Candidates accept or reject.
32. System evaluates group feasibility.
33. Participants agree on a host and proposed session slot.
34. Every participant approves the slot.
35. The Study Session is confirmed.
36. Related Study Intents are marked as converted.
    Flow C — No Available Match
37. Student submits a Study Intent.
38. Session Matching returns no qualified result.
39. Partner Matching returns no qualified result.
40. System keeps the intent active.
41. New matching opportunities may trigger a new evaluation.
42. The student may edit or cancel the intent.
43. The intent expires after its latest acceptable date if it remains unfulfilled.

44. Baseline System Configuration
    The following parameters are initial experimental settings, not validated optimal values.
    Parameter Initial Configuration
    Initial target population First- and second-year Telkom University students
    Matching priority Session-First
    Matching fallback Partner Matching
    Minimum group size 2 students
    Maximum group size 4 students
    Minimum continuous session duration 60 minutes
    Maximum displayed recommendations 5
    Recommendation threshold To be calibrated
    Matching approach Rule-based
    Ranking explanation Required
    Session confirmation Host and participant approval
    Feedback Recommendation and session-level
45. Day 1 Completion Criteria
    Day 1 is considered complete when the following conditions are met:
46. Product purpose and scope are documented.
47. User roles are defined.
48. Primary system entities are distinguished.
49. Study Intent and Study Session have unambiguous definitions.
50. Core business rules are documented.
51. Session-First and Partner Matching have separate workflows.
52. Group formation requirements are established.
53. Study Intent and Study Session lifecycles are defined.
54. Feedback categories are established.
55. Initial system boundaries are documented.

56. Decisions Deferred to Subsequent Design Phases
    The following topics are intentionally not finalized during Day 1:

- Detailed database schema and ERD.
- Exact input field types and validation implementation.
- Final hard constraint formulas.
- Topic similarity formulas.
- Schedule compatibility scoring.
- Compatibility matrices.
- Final scoring weights.
- Recommendation thresholds.
- Group compatibility formulas.
- Detailed API contracts.
- Feedback calibration algorithms.
  These topics will be developed in the following design stages to avoid making mathematical or technical decisions before the business requirements are stable.

End of Day 1 Specification — Version 1.0

Hasil audit Day 1
Setelah menyusun dokumennya, ada beberapa keputusan penting yang sudah saya tetapkan dan perlu kamu perhatikan karena akan memengaruhi seluruh perancangan berikutnya.

1. Perbedaan paling penting: Study Intent dan Study Session
   Study Intent

Kebutuhan individual mahasiswa.

Input sistem

Study Session

Aktivitas belajar bersama yang konkret.

Hasil sistem

Matching & Group Formation

Satu kebutuhan belajar dapat menghasilkan satu sesi belajar yang dikonfirmasi bersama.

Ini harus menjadi landasan database dan algoritma. Jangan sampai nanti Study Intent dan Study Session digabung ke dalam satu tabel atau satu objek konseptual tanpa membedakan fungsinya. 2. Keputusan Session-First sudah dibuat tegas
Saya menetapkan bahwa sesi dan partner tidak ditampilkan sebagai dua kategori rekomendasi yang bercampur.

Study Intent
|
v
Session Matching
|
+---- Qualified Session Found
| |
| v
| Recommend Sessions
|
+---- No Qualified Session
|
v
Partner Matching
|
+------+------+
| |
Partner Found No Partner
| |
v v
Group Formation Keep Intent Active

Dengan begitu, pengguna yang membutuhkan sesi belajar akan selalu diarahkan ke sesi siap diikuti terlebih dahulu. Partner Matching digunakan untuk menciptakan peluang sesi baru saat belum ada sesi yang sesuai. 3. Ada satu hal yang perlu diperhatikan untuk Day 2
Saya menetapkan bahwa ketika Partner Matching berhasil, mahasiswa yang memulai proses akan menjadi provisional host secara default. Tetapi peserta tetap dapat menyepakati host lain.

Ini sengaja dibuat agar proses pembentukan kelompok tidak menggantung ketika beberapa mahasiswa sudah saling menerima undangan.

Nantinya, hal ini harus direpresentasikan dengan jelas pada ERD melalui relasi Student, Study Intent, Invitation, Study Session, dan Session Membership. 4. Hal yang belum boleh kita tetapkan sembarangan
Ada tiga hal yang sengaja belum saya finalkan:

- Bobot compatibility score.
- Nilai compatibility matrix.
- Ambang minimum rekomendasi.
  Ketiganya membutuhkan simulasi dan validasi. Menentukan angka sekarang hanya berdasarkan intuisi berisiko menghasilkan ranking yang tidak sesuai perilaku pengguna.

Day 1 — System Design
Baseline completed

100%
Seluruh deliverable konseptual dan aturan bisnis Day 1 sudah disusun dalam spesifikasi v1.0. Angka ini menunjukkan kelengkapan dokumen, bukan validasi empiris sistem.

Kesimpulan saya: kita sudah mempunyai fondasi konseptual yang cukup kuat untuk masuk ke Day 2. Tahap berikutnya adalah mengubah tujuh entitas yang sudah didefinisikan menjadi struktur database, menentukan relasi dan cardinality, lalu menyusun ERD yang konsisten dengan business rules ini.
