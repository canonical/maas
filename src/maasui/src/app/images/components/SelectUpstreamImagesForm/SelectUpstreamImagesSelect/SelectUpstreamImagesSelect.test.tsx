import { Formik } from "formik";

import {
  getDownloadableImages,
  groupArchesByTitle,
  groupImagesByOS,
} from "@/app/images/components/SelectUpstreamImagesForm/SelectUpstreamImagesForm";
import type { DownloadImagesSelectProps } from "@/app/images/components/SelectUpstreamImagesForm/SelectUpstreamImagesSelect/SelectUpstreamImagesSelect";
import SelectUpstreamImagesSelect, {
  getValueKey,
} from "@/app/images/components/SelectUpstreamImagesForm/SelectUpstreamImagesSelect/SelectUpstreamImagesSelect";
import { availableImageFactory } from "@/testing/factories";
import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("SelectUpstreamImagesSelect", () => {
  it("correctly calls setFieldValue", async () => {
    const releases = [availableImageFactory.build()];

    const downloadableImages = getDownloadableImages(releases);
    const imagesByOS = groupImagesByOS(downloadableImages);
    const groupedImages = groupArchesByTitle(imagesByOS);
    const mockSetFieldValue = vi.fn();
    renderWithProviders(
      <Formik initialValues={{ images: [] }} onSubmit={vi.fn()}>
        {({ values }: Pick<DownloadImagesSelectProps, "values">) => (
          <SelectUpstreamImagesSelect
            groupedImages={groupedImages}
            setFieldValue={mockSetFieldValue}
            values={values}
          />
        )}
      </Formik>
    );

    await userEvent.click(screen.getByText("Ubuntu"));

    const combobox = screen.getByRole("combobox");

    await userEvent.click(combobox);

    const checkbox = screen.getAllByRole("checkbox")[0];

    await userEvent.click(checkbox);

    expect(mockSetFieldValue).toHaveBeenCalledWith(
      getValueKey("Ubuntu", releases[0].release, releases[0].title),
      [groupedImages.Ubuntu[`${releases[0].title}&${releases[0].release}`][0]]
    );
  });
});
