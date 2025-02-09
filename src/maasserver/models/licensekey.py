# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Global license keys."""

from django.db.models import CharField, Manager

from maasserver.models.timestampedmodel import TimestampedModel


class LicenseKeyManager(Manager):
    """Manager for model class.

    Don't import or instantiate this directly; access as `LicenseKey.objects`.
    """

    def get_by_osystem_series(self, osystem, distro_series):
        """Returns :class:`LicenseKey`; for osystem and distro_series."""
        return self.get(osystem=osystem, distro_series=distro_series)

    def get_license_key(self, osystem, distro_series):
        """Returns the value of license_key in the :class:`LicenseKey`; model.

        :param osystem: operating system
        :param distro_series: os distro series
        :return: license key
        :rtype: unicode
        """
        key = self.get_by_osystem_series(osystem, distro_series)
        return key.license_key

    def has_license_key(self, osystem, distro_series):
        """Checks that a license key exists for the osystem and
        distro_series."""
        return self.filter(
            osystem=osystem, distro_series=distro_series
        ).exists()


class LicenseKey(TimestampedModel):
    """Available license key for osystem and distro_series combo.

    Each `LicenseKey` matches to a operating system and release. Only one
    license key can exists per osystem/distro_series combination.
    """

    class Meta:
        unique_together = (("osystem", "distro_series"),)

    objects = LicenseKeyManager()

    # Operating system (e.g. "ubuntu") that uses the license key.
    osystem = CharField(max_length=255, blank=False)

    # OS series (e.g. "precise") that uses the license key.
    distro_series = CharField(max_length=255, blank=False)

    # License key for the osystem/distro_series combo.
    license_key = CharField(
        max_length=255,
        blank=False,
        verbose_name="License Key",
        help_text="License key for operating system",
    )

    def __repr__(self):
        return f"<LicenseKey {self.osystem}/{self.distro_series}>"

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ("osystem", "distro_series"):
            return "{} {}".format(
                "License key with this operating system and distro series",
                "already exists.",
            )
        return super().unique_error_message(model_class, unique_check)
