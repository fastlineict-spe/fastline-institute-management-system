from django.db import models


class Department(models.Model):
    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="departments",
        null=False,
blank=False
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "code"],
                name="unique_department_code_per_campus"
            ),
            models.UniqueConstraint(
                fields=["campus", "name"],
                name="unique_department_name_per_campus"
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

