import * as Yup from "yup";

const commaSeparated = Yup.string()
  .transform((value) =>
    value
      .split(",")
      .map((s: string) => s.trim())
      .join(", ")
  )
  .matches(/^(?:[^,\s]+(?:,\s*[^,\s]+)*)?$/, "Must be comma-separated.");

export const repositorySchema = Yup.object().shape({
  arches: Yup.array(),
  components: commaSeparated,
  default: Yup.boolean().required(),
  disable_sources: Yup.boolean().required(),
  disabled_components: Yup.array(),
  disabled_pockets: Yup.array(),
  distributions: commaSeparated,
  enabled: Yup.boolean().required(),
  key: Yup.string(),
  name: Yup.string().required("Name field required."),
  url: Yup.string().required("URL field required."),
});
