import { useEffect, useState } from "react";
import * as React from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import {
  Col,
  Input,
  Notification as NotificationBanner,
  Row,
  Select,
} from "@canonical/react-components";
import classNames from "classnames";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import type { DeployFormValues } from "../DeployForm";

import { useGetCurrentUser } from "@/app/api/query/auth";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TooltipButton from "@/app/base/components/TooltipButton";
import UploadTextArea from "@/app/base/components/UploadTextArea";
import docsUrls from "@/app/base/docsUrls";
import urls from "@/app/base/urls";
import configSelectors from "@/app/store/config/selectors";
import {
  osInfo as osInfoSelectors,
  defaultMinHweKernel as defaultMinHweKernelSelectors,
} from "@/app/store/general/selectors";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import { timeSpanToMinutes } from "@/app/utils";

export const DeployFormFields = (): React.ReactElement => {
  const [deployVmHost, setDeployVmHost] = useState(false);
  const [userDataVisible, setUserDataVisible] = useState(false);
  const formikProps = useFormikContext<DeployFormValues>();
  const { handleChange, setFieldValue, values } = formikProps;

  const user = useGetCurrentUser();

  const osOptions = useSelector(configSelectors.defaultOSystemOptions);
  const defaultMinHweKernel = useSelector(defaultMinHweKernelSelectors.get);
  const { osystems = [], releases = [] } =
    useSelector(osInfoSelectors.get) || {};
  const allReleaseOptions = useSelector(osInfoSelectors.getAllOsReleases) || {};
  const releaseOptions = allReleaseOptions[values.oSystem] || [];
  const kernelOptions = useSelector((state: RootState) =>
    osInfoSelectors.getUbuntuKernelOptions(state, values.release)
  );
  const canBeKVMHost =
    values.oSystem === "ubuntu" &&
    ["bionic", "focal", "jammy", "noble"].includes(values.release);
  const noImages = osystems.length === 0 || releases.length === 0;
  const clearVmHostOptions = () => {
    setDeployVmHost(false);
    setFieldValue("vmHostType", "").catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "vmHostType",
        "setFieldValue",
        reason as string
      );
    });
  };
  const hardwareSyncInterval = useSelector(
    configSelectors.hardwareSyncInterval
  );

  // When the kernel options change then reset the selected kernel. If the
  // selected release contains the default kernel then select it.
  useEffect(() => {
    if (defaultMinHweKernel) {
      if (kernelOptions.find(({ value }) => value === defaultMinHweKernel)) {
        setFieldValue("kernel", defaultMinHweKernel).catch(
          (reason: unknown) => {
            throw new FormikFieldChangeError(
              "kernel",
              "setFieldValue",
              reason as string
            );
          }
        );
      } else {
        setFieldValue("kernel", "").catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "kernel",
            "setFieldValue",
            reason as string
          );
        });
      }
    }
  }, [defaultMinHweKernel, kernelOptions, setFieldValue]);

  return (
    <>
      {noImages && (
        <NotificationBanner data-testid="images-error" severity="negative">
          You will not be able to deploy a machine until at least one valid
          image has been downloaded. To download an image, visit the{" "}
          <Link to={urls.images.index}>images page</Link>.
        </NotificationBanner>
      )}
      <div className="u-sv2">
        <Row>
          <Col size={12}>
            <FormikField
              component={Select}
              disabled={noImages}
              label="OS"
              name="oSystem"
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                handleChange(e);
                const value = e.target.value;
                setFieldValue("kernel", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "kernel",
                    "setFieldValue",
                    reason as string
                  );
                });
                if (
                  allReleaseOptions[value] &&
                  allReleaseOptions[value].length
                ) {
                  setFieldValue(
                    "release",
                    allReleaseOptions[value][0].value
                  ).catch((reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "release",
                      "setFieldValue",
                      reason as string
                    );
                  });
                }
                if (value !== "ubuntu") {
                  clearVmHostOptions();
                }
              }}
              options={osOptions}
            />
          </Col>
          <Col size={12}>
            <FormikField
              component={Select}
              disabled={noImages}
              label="Release"
              name="release"
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                handleChange(e);
                setFieldValue("kernel", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "kernel",
                    "setFieldValue",
                    reason as string
                  );
                });
                if (!["bionic", "focal"].includes(e.target.value)) {
                  clearVmHostOptions();
                }
              }}
              options={releaseOptions}
            />
          </Col>
          <Col size={12}>
            {values.oSystem === "ubuntu" && (
              <FormikField
                component={Select}
                label="Kernel"
                name="kernel"
                options={kernelOptions}
              />
            )}
          </Col>
        </Row>
        <div className="u-sv2">
          <hr className="u-sv2" />
        </div>
        <Row>
          <Col size={12}>
            <p>Deployment target</p>
          </Col>
          <Col size={12}>
            <Input
              checked={!values.ephemeralDeploy}
              label="Deploy to disk"
              name="ephemeralDeploy"
              onChange={() => {
                setFieldValue("ephemeralDeploy", false).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "ephemeralDeploy",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              }}
              type="radio"
            />
            <Input
              checked={values.ephemeralDeploy}
              help="No disk layout will be applied during deployment. All system data will be reset upon reboot or shutdown."
              label="Deploy in memory"
              name="ephemeralDeploy"
              onChange={() => {
                setFieldValue("ephemeralDeploy", true).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "ephemeralDeploy",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              }}
              type="radio"
            />
          </Col>
        </Row>
        <div className="u-sv2">
          <hr className="u-sv2" />
        </div>
        <Row>
          <Col size={12}>
            <p>Customise options</p>
          </Col>
          <Col size={12}>
            {!values.ephemeralDeploy && (
              <>
                <Input
                  checked={deployVmHost}
                  disabled={!canBeKVMHost || noImages}
                  help={
                    values.vmHostType === PodType.VIRSH
                      ? "Only Ubuntu 18.04 LTS and Ubuntu 20.04 LTS are officially supported."
                      : undefined
                  }
                  id="deployVmHost"
                  label={
                    <>
                      Register as MAAS KVM host.{" "}
                      <ExternalLink to={docsUrls.kvmIntroduction}>
                        KVM docs
                      </ExternalLink>
                    </>
                  }
                  onChange={(evt: React.ChangeEvent<HTMLInputElement>) => {
                    const { checked } = evt.target;
                    if (checked) {
                      setDeployVmHost(true);
                      setFieldValue("vmHostType", PodType.LXD).catch(
                        (reason: unknown) => {
                          throw new FormikFieldChangeError(
                            "vmHostType",
                            "setFieldValue",
                            reason as string
                          );
                        }
                      );
                    } else {
                      clearVmHostOptions();
                    }
                  }}
                  type="checkbox"
                />
                {deployVmHost && (
                  <>
                    <FormikField
                      label="LXD"
                      name="vmHostType"
                      type="radio"
                      value={PodType.LXD}
                      wrapperClassName="u-nudge-right--x-large"
                    />
                    <FormikField
                      label="libvirt"
                      name="vmHostType"
                      type="radio"
                      value={PodType.VIRSH}
                      wrapperClassName="u-nudge-right--x-large"
                    />
                  </>
                )}
              </>
            )}
            <FormikField
              aria-label="Cloud-init user-data"
              disabled={noImages}
              label={
                <>
                  Cloud-init user-data&hellip;{" "}
                  <ExternalLink to={docsUrls.cloudInit}>
                    Cloud-init docs
                  </ExternalLink>
                </>
              }
              name="includeUserData"
              onChange={(evt: React.ChangeEvent<HTMLInputElement>) => {
                handleChange(evt);
                setUserDataVisible(evt.target.checked);
              }}
              type="checkbox"
              wrapperClassName={classNames({
                "u-sv2": userDataVisible,
              })}
            />
            {userDataVisible && (
              <UploadTextArea
                label="Upload script"
                name="userData"
                placeholder="Paste or drop script here."
                rows={10}
              />
            )}
            <FormikField
              help={
                <>
                  Hardware sync interval:{" "}
                  {!hardwareSyncInterval
                    ? "Invalid"
                    : `${timeSpanToMinutes(hardwareSyncInterval)} minutes`}{" "}
                  - Admins can change this in the global settings.
                </>
              }
              label={
                <>
                  Periodically sync hardware{" "}
                  <TooltipButton
                    aria-label="more about periodically sync hardware"
                    message={`Enable this to make MAAS periodically check the
                  hardware configuration of this machine and reflect any
                  possible change after the deployment.`}
                    positionElementClassName="u-display--inline"
                  />{" "}
                  <ExternalLink to={docsUrls.hardwareSync}>
                    Hardware sync docs
                  </ExternalLink>
                </>
              }
              name="enableHwSync"
              type="checkbox"
            />

            <FormikField
              help={
                <>
                  To enable kernel crash dump, the hardware{" "}
                  <TooltipButton
                    iconName="help-mid-dark"
                    message={
                      <span className="u-align-text--center u-flex--center">
                        {" "}
                        &gt;= 4 CPU threads, <br /> &gt;= 6GB RAM, <br />
                        Reserve &gt;5x RAM size as free disk space in /var.
                      </span>
                    }
                  />{" "}
                  must meet the minimum requirements and the OS{" "}
                  <TooltipButton
                    iconName="help-mid-dark"
                    message="Tested with Ubuntu 24.04 LTS or higher."
                  />{" "}
                  must support it. Check crash dump status in machine details.{" "}
                  <ExternalLink to="https://ubuntu.com/server/docs/kernel-crash-dump">
                    More about kernel crash dump
                  </ExternalLink>
                </>
              }
              label={
                <>
                  Try to enable kernel crash dump{" "}
                  <ExternalLink to="https://ubuntu.com/server/docs/kernel-crash-dump">
                    Kernel crash dump docs
                  </ExternalLink>
                </>
              }
              name="enableKernelCrashDump"
              type="checkbox"
            />
          </Col>
        </Row>
        {user && user.data?.statistics?.sshkeys_count === 0 && (
          <Row>
            <Col size={12}>
              <p className="u-no-max-width" data-testid="sshkeys-warning">
                <i className="p-icon--warning is-inline"></i>
                Login will not be possible because no SSH keys have been added
                to your account. To add an SSH key, visit your{" "}
                <Link to={urls.preferences.sshKeys}>account page</Link>.
              </p>
            </Col>
          </Row>
        )}
      </div>
    </>
  );
};

export default DeployFormFields;
