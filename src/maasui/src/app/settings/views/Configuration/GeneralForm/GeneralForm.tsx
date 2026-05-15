import { useEffect, useRef } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Col, Row } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import ThemedRadioButton from "./ThemedRadioButton";
import { ColorValues } from "./ThemedRadioButton/ThemedRadioButton";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSendAnalytics } from "@/app/base/hooks";
import { useThemeContext } from "@/app/base/theme-context";
import type { UsabillaLive } from "@/app/base/types";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";

declare global {
  interface Window {
    usabilla_live: UsabillaLive;
  }
}

export enum Labels {
  FormLabel = "Configuration - General",
}

const GeneralSchema = Yup.object().shape({
  maas_name: Yup.string().required(),
  theme: Yup.string(),
  enable_analytics: Yup.boolean(),
  release_notifications: Yup.boolean(),
});

type GeneralFormValues = {
  maas_name: string;
  theme: string;
  enable_analytics: boolean;
  release_notifications: boolean;
};

const GeneralForm = (): React.ReactElement => {
  const dispatch = useDispatch();
  const maasName = useSelector(configSelectors.maasName);
  const maasTheme = useSelector(configSelectors.theme);
  const analyticsEnabled = useSelector(configSelectors.analyticsEnabled);
  const releaseNotifications = useSelector(
    configSelectors.releaseNotifications
  );
  const saved = useSelector(configSelectors.saved);
  const saving = useSelector(configSelectors.saving);
  const errors = useSelector(configSelectors.errors);
  const previousReleaseNotifications = useRef(releaseNotifications);
  const previousEnableAnalytics = usePrevious(analyticsEnabled);
  const { setTheme } = useThemeContext();

  useEffect(() => {
    // revert to persisted theme value on unmount
    return () => {
      setTheme(maasTheme ? maasTheme : "default");
    };
  }, [setTheme, maasTheme]);

  useEffect(() => {
    if (analyticsEnabled !== previousEnableAnalytics) {
      // If the analytics setting has been changed, the only way to be
      // completely sure the events are cleared is to reload the window.
      // This needs to be done once the data has been been updated successfully,
      // hence doing the refresh in this useEffect.
      window.location.reload();
    }
  }, [analyticsEnabled, previousEnableAnalytics]);

  const sendAnalytics = useSendAnalytics();

  return (
    <FormikForm<GeneralFormValues>
      aria-label="Configuration - General"
      cleanup={configActions.cleanup}
      errors={errors}
      initialValues={{
        maas_name: maasName || "",
        theme: maasTheme || ColorValues.Default,
        enable_analytics: analyticsEnabled || false,
        release_notifications: releaseNotifications || false,
      }}
      onCancel={(values, { resetForm }) => {
        resetForm();
        setTheme(maasTheme ? maasTheme : "default");
        values.theme = maasTheme ? maasTheme : "default";
      }}
      onSaveAnalytics={{
        action: "Saved",
        category: "Configuration settings",
        label: "General form",
      }}
      onSubmit={(values, { resetForm }) => {
        if (values.enable_analytics !== previousEnableAnalytics) {
          // Only send the analytics event if the value changes.
          sendAnalytics(
            "General configuration settings",
            values.enable_analytics ? "Turned on" : "Turned off",
            "Enable Google Analytics"
          );
        }
        // Show the Usabilla form if the notifications have been turned off and
        // analytics has been enabled and Usabilla as been instantiated.
        if (
          !values.release_notifications &&
          previousReleaseNotifications.current &&
          values.enable_analytics &&
          window.usabilla_live
        ) {
          window.usabilla_live("trigger", "release_notifications_off");
        }
        previousReleaseNotifications.current = values.release_notifications;
        dispatch(configActions.update(values));
        resetForm({ values });
      }}
      saved={saved}
      saving={saving}
      validationSchema={GeneralSchema}
    >
      <FormikField
        help={
          <>
            Use MAAS name and unicode emoji(s) to describe your MAAS instance.{" "}
            <br />
            <br />
            Examples: <br />
            US-west-2 🇺🇸 MAAS-prod <br />
            my-maas ❗ no-deploys
          </>
        }
        label="MAAS name"
        name="maas_name"
        required={true}
        type="text"
        wrapperClassName="u-sv2"
      />
      <p className="general-form__theme-label">MAAS theme main colour</p>
      <Row className="general-form__radio-row">
        {[
          { value: ColorValues.Default, label: "Default" },
          { value: ColorValues.Bark, label: "Bark" },
          { value: ColorValues.Sage, label: "Sage" },
          { value: ColorValues.Olive, label: "Olive" },
          { value: ColorValues.Viridian, label: "Viridian" },
          { value: ColorValues.PrussianGreen, label: "Prussian green" },
          { value: ColorValues.Blue, label: "Blue" },
          { value: ColorValues.Purple, label: "Purple" },
          { value: ColorValues.Magenta, label: "Magenta" },
          { value: ColorValues.Red, label: "Red" },
        ].map((color, i) => (
          <Col key={i} medium={1} size={2} small={2}>
            <FormikField
              color={color.value}
              component={ThemedRadioButton}
              label={color.label}
              name="theme"
              onClick={() => {
                setTheme(color.value);
              }}
            />
          </Col>
        ))}
      </Row>
      <h5>Data analytics</h5>
      <FormikField
        help={
          <>
            The analytics used in MAAS are Google Analytics, Usabilla and Sentry
            Error Tracking.{" "}
            <ExternalLink to="https://ubuntu.com/legal/data-privacy">
              Data privacy
            </ExternalLink>
          </>
        }
        label="Enable analytics to shape improvements to user experience"
        name="enable_analytics"
        type="checkbox"
        wrapperClassName="u-sv3"
      />
      <h5>Notifications</h5>
      <FormikField
        help="This applies to all users of MAAS. "
        label="Enable new release notifications"
        name="release_notifications"
        type="checkbox"
        wrapperClassName="u-sv3"
      />
    </FormikForm>
  );
};

export default GeneralForm;
