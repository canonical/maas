import type { ReactElement } from "react";
import { useEffect, useCallback, useState, useMemo } from "react";

import {
  Accordion,
  FormikField,
  MultiSelect,
  type MultiSelectItem,
} from "@canonical/react-components";
import type { Section } from "@canonical/react-components/dist/components/Accordion/Accordion";

import type { GroupedImages } from "@/app/images/components/SelectUpstreamImagesForm/SelectUpstreamImagesForm";
import { OPERATING_SYSTEM_NAMES } from "@/app/images/constants";

import "./_index.scss";

export const getValueKey = (
  distro: string,
  release: string,
  title: string
): string => `${distro}&${release}&${title}`.replace(".", "-");

export type DownloadImagesSelectProps = {
  values: Record<string, MultiSelectItem[]>;
  setFieldValue: (key: string, value: MultiSelectItem[]) => void;
  groupedImages: GroupedImages;
};

const SelectUpstreamImagesSelect = ({
  values,
  setFieldValue,
  groupedImages,
}: DownloadImagesSelectProps): ReactElement => {
  const [openMultiSelectKey, setOpenMultiSelectKey] = useState<string | null>(
    null
  );
  const [forceRenderKeys, setForceRenderKeys] = useState<
    Record<string, number>
  >({});

  useEffect(() => {
    if (!openMultiSelectKey) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      // Find the specific MultiSelect container for the open one
      const openMultiSelectElement = document.querySelector(
        `[data-multiselect-key="${openMultiSelectKey}"]`
      );

      if (!openMultiSelectElement) return;

      // Check if click is inside the MultiSelect container or dropdown
      if (
        target instanceof Element &&
        (openMultiSelectElement.contains(target) ||
          target.closest(".multi-select__dropdown"))
      ) {
        return;
      }

      // Click is outside - force re-render to close
      setForceRenderKeys((prev) => ({
        ...prev,
        [openMultiSelectKey]: (prev[openMultiSelectKey] || 0) + 1,
      }));
      setOpenMultiSelectKey(null);
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openMultiSelectKey]);

  const handleAccordionExpandedChange = useCallback(() => {
    // Close any open MultiSelect when accordion sections are toggled
    if (openMultiSelectKey) {
      setForceRenderKeys((prev) => ({
        ...prev,
        [openMultiSelectKey]: (prev[openMultiSelectKey] || 0) + 1,
      }));
      setOpenMultiSelectKey(null);
    }
  }, [openMultiSelectKey]);

  const accordionSections = useMemo(
    () =>
      Object.keys(groupedImages).map((distro) => {
        return {
          key: distro,
          content: (
            <table className="download-images-table">
              <thead>
                <tr>
                  <th>Release Title</th>
                  <th>Architecture</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(groupedImages[distro]).map((key) => {
                  const [title, release] = key.split("&");
                  const multiSelectKey = getValueKey(distro, release, title);
                  return (
                    <tr key={key}>
                      <td>
                        <div>{title}</div>
                        <small className="u-text--muted">{release}</small>
                      </td>
                      <td
                        data-multiselect-key={multiSelectKey}
                        onClick={() => {
                          setOpenMultiSelectKey(multiSelectKey);
                        }}
                      >
                        <FormikField
                          component={MultiSelect}
                          items={groupedImages[distro][key]}
                          key={`${multiSelectKey}-${forceRenderKeys[multiSelectKey] || 0}`}
                          name={multiSelectKey}
                          onItemsUpdate={(items: MultiSelectItem[]) => {
                            setFieldValue(multiSelectKey, items);
                          }}
                          placeholder="Select architectures"
                          selectedItems={values[multiSelectKey]}
                          variant="condensed"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ),
          titleElement: "h4",
          title:
            OPERATING_SYSTEM_NAMES.find(
              (os) => os.value.toLowerCase() === distro.toLowerCase()
            )?.label ?? distro,
        } as Section;
      }),
    [groupedImages, values, setFieldValue, forceRenderKeys]
  );
  return (
    <Accordion
      onExpandedChange={handleAccordionExpandedChange}
      sections={accordionSections}
    />
  );
};
export default SelectUpstreamImagesSelect;
