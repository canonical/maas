import { useState } from "react";

import {
  Col,
  Icon,
  Input,
  Notification as NotificationBanner,
  Row,
} from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import type { NewPodValues } from "../../types";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import urls from "@/app/base/urls";
import podSelectors from "@/app/store/pod/selectors";
import type { RootState } from "@/app/store/root/types";

type Props = {
  newPodValues: NewPodValues;
};

export const SelectProjectFormFields = ({
  newPodValues,
}: Props): React.ReactElement => {
  const podsInServer = useSelector((state: RootState) =>
    podSelectors.getByLxdServer(state, newPodValues.power_address)
  );
  const projects = useSelector((state: RootState) =>
    podSelectors.getProjectsByLxdServer(state, newPodValues.power_address)
  );
  const { setFieldValue } = useFormikContext();
  const [newProject, setNewProject] = useState(true);
  const freeProjects = projects.filter(
    (project) =>
      !podsInServer.some(
        (pod) => pod.power_parameters?.project === project.name
      )
  );

  return (
    <Row>
      {!newProject && (
        <Col size={12}>
          <NotificationBanner
            data-testid="existing-project-warning"
            severity="caution"
          >
            MAAS will recommission all VMs in the selected project.
          </NotificationBanner>
        </Col>
      )}
      <Col size={12}>
        <p data-testid="lxd-host-details">
          <strong>
            LXD host: {newPodValues.name} ({newPodValues.power_address})
          </strong>
        </p>
        <p className="u-text--muted">
          <span>Connected</span>
          <span className="u-nudge-right--small">
            <Icon name="success" />
          </span>
        </p>
      </Col>
      <Col size={12}>
        <Input
          checked={newProject}
          id="new-project"
          label="Add new project"
          name="project-select"
          onChange={() => {
            setNewProject(true);
            setFieldValue("existingProject", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "existingProject",
                "setFieldValue",
                reason as string
              );
            });
          }}
          type="radio"
        />
        <FormikField
          aria-label="New project name"
          disabled={!newProject}
          help={`A project name must be less than 63 characters and must not
                 contain spaces or special characters (i.e. / . ' " *)`}
          name="newProject"
          type="text"
          wrapperClassName="u-nudge-right--x-large u-sv2"
        />
        <Input
          checked={!newProject}
          disabled={freeProjects.length === 0}
          id="existing-project"
          label="Select existing project"
          name="project-select"
          onChange={() => {
            setNewProject(false);
            setFieldValue("newProject", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "newProject",
                "setFieldValue",
                reason as string
              );
            });
            setFieldValue("existingProject", freeProjects[0]?.name || "").catch(
              (reason: unknown) => {
                throw new FormikFieldChangeError(
                  "existingProject",
                  "setFieldValue",
                  reason as string
                );
              }
            );
          }}
          type="radio"
        />
        {projects.map((project) => {
          const projectPod = podsInServer.find(
            (pod) => pod.power_parameters?.project === project.name
          );
          return (
            <div className="u-flex" key={project.name}>
              <FormikField
                disabled={newProject || Boolean(projectPod)}
                label={project.name}
                name="existingProject"
                type="radio"
                value={project.name}
                wrapperClassName="u-nudge-right--x-large"
              />
              {!newProject && projectPod && (
                <label className="u-nudge-right" data-testid="existing-pod">
                  <Link to={urls.kvm.lxd.single.index({ id: projectPod.id })}>
                    already exists
                  </Link>
                </label>
              )}
            </div>
          );
        })}
      </Col>
    </Row>
  );
};

export default SelectProjectFormFields;
