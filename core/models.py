from django.db import models


class Client(models.Model):
    client_id = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True, default="")
    email_domain = models.CharField(max_length=150, blank=True, default="")
    contract_start = models.CharField(max_length=20, blank=True, default="")
    contract_end = models.CharField(max_length=20, blank=True, default="")
    seats = models.IntegerField(default=0)


class Staff(models.Model):
    staff_id = models.CharField(max_length=32, primary_key=True)
    full_name = models.CharField(max_length=200)
    email = models.CharField(max_length=200, db_index=True)
    role = models.CharField(max_length=32, db_index=True)  # administrator | instructor
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT, db_column="client_id")
    specialism = models.CharField(max_length=100, blank=True, default="")
    joined_on = models.CharField(max_length=20, blank=True, default="")
    left_on = models.CharField(max_length=20, blank=True, default="")
    password_hash = models.CharField(max_length=128, default="password123")

    @property
    def is_active_staff(self) -> bool:
        return not bool(self.left_on and self.left_on.strip())


class Course(models.Model):
    course_id = models.CharField(max_length=120, primary_key=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    cohort = models.CharField(max_length=64, blank=True, default="")
    starts_on = models.CharField(max_length=20, blank=True, default="")
    ends_on = models.CharField(max_length=20, blank=True, default="")
    length_days = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="published", db_index=True)  # draft | published


class CourseStaff(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="staff_assignments", db_column="course_id")
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="course_assignments", db_column="staff_id")
    role = models.CharField(max_length=40, default="lead")
    assigned_on = models.CharField(max_length=20, blank=True, default="")
    unassigned_on = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "staff", "assigned_on"], name="uniq_course_staff_assigned")
        ]


class CoursePage(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="pages", db_column="course_id")
    order = models.IntegerField(default=1)
    title = models.CharField(max_length=255)
    body_text = models.TextField(blank=True, default="")
    image_path = models.CharField(max_length=500, blank=True, default="")
    pdf_path = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["order", "id"]


class Assessment(models.Model):
    assessment_id = models.CharField(max_length=64, primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assessments", db_column="course_id")
    type = models.CharField(max_length=40)  # Quiz | Assignment | Final exam
    title = models.CharField(max_length=255)
    due_on = models.CharField(max_length=20, blank=True, default="")
    weight_pct = models.FloatField(default=0.0)
    author = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, db_column="author_id")
    status = models.CharField(max_length=20, default="published", db_index=True)  # draft | published
    published_on = models.CharField(max_length=20, blank=True, default="")


class QuizQuestion(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions", db_column="assessment_id")
    prompt = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=4, default="A")  # A | B | C | D


class Learner(models.Model):
    learner_id = models.CharField(max_length=64, primary_key=True)
    full_name = models.CharField(max_length=200)
    email = models.CharField(max_length=200, db_index=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="learners", db_column="client_id")
    department = models.CharField(max_length=120, db_index=True)
    account_created_on = models.CharField(max_length=20, blank=True, default="")
    created_by = models.CharField(max_length=64, blank=True, default="")
    account_status = models.CharField(max_length=20, default="active", db_index=True)  # active | deactivated
    password_hash = models.CharField(max_length=128, default="password123")


class Enrolment(models.Model):
    enrolment_id = models.CharField(max_length=64, primary_key=True)
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="enrolments", db_column="learner_id")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrolments", db_column="course_id")
    enrolled_on = models.CharField(max_length=20, blank=True, default="")
    withdrawn_on = models.CharField(max_length=20, blank=True, default="")
    outcome = models.CharField(max_length=40, default="In Progress", db_index=True)
    previous_attempts = models.IntegerField(default=0)
    activity_clicks = models.IntegerField(default=0)
    enrolled_by = models.CharField(max_length=64, default="self")

    class Meta:
        indexes = [
            models.Index(fields=["course", "learner"]),
            models.Index(fields=["learner", "course"]),
        ]


class Attempt(models.Model):
    attempt_id = models.CharField(max_length=64, primary_key=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="attempts", db_column="assessment_id")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="attempts", db_column="learner_id")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="attempts", db_column="course_id")
    submitted_on = models.CharField(max_length=20, blank=True, default="")
    score = models.FloatField(null=True, blank=True)
    graded_by = models.CharField(max_length=64, blank=True, default="")
    submission_text = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["course", "learner"]),
            models.Index(fields=["assessment", "learner"]),
        ]
