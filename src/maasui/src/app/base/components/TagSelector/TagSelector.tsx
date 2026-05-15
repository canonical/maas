import type { ReactNode } from "react";
import { useState } from "react";

import { Button, Input, useClickOutside } from "@canonical/react-components";
import Field from "@canonical/react-components/dist/components/Field";
import classNames from "classnames";

export type Tag = {
  id?: number;
  name: string;
  displayName?: string;
  description?: string;
};

export type Props = {
  allowNewTags?: boolean;
  disabled?: boolean;
  error?: string;
  externalSelectedTags?: Tag[];
  help?: string;
  initialSelected?: Tag[];
  label?: string | null;
  onAddNewTag?: (name: string) => (event: React.SyntheticEvent) => void;
  onTagsUpdate?: (tags: Tag[]) => void;
  placeholder?: string;
  required?: boolean;
  generateDropdownEntry?: (tag: Tag, highlightedName: ReactNode) => ReactNode;
  header?: ReactNode;
  showSelectedTags?: boolean;
  tags: Tag[];
  disabledTags?: Tag[];
};

// Give an explicit name to the text input so we can exclude it from form submission
export const TAG_SELECTOR_INPUT_NAME = "tagSelectorInput";

type UpdateTags = (newSelectedTags: Tag[], clearFilter?: boolean) => void;

/**
 * Highlights a portion of given text that matches substring.
 * @param text - Text to search for substring.
 * @param match - Substring to highlight.
 * @returns JSX with emphasised text.
 */
const highlightMatch = (text: string, match: string): React.ReactElement => {
  const textArray = text.split(match);
  return (
    <span>
      {textArray.map((item, i) => (
        <span key={`${item}${i}`}>
          {item}
          {i !== textArray.length - 1 && <strong>{match}</strong>}
        </span>
      ))}
    </span>
  );
};

const sanitiseFilter = (filterText: string) => ({
  name: filterText.replace(/ /g, "-"),
});

const generateDropdownItems = ({
  allowNewTags,
  onAddNewTag,
  setFilter,
  filter,
  selectedTags,
  tags,
  updateTags,
  generateDropdownEntry,
}: {
  allowNewTags: Props["allowNewTags"];
  onAddNewTag: Props["onAddNewTag"];
  setFilter: (filter: string) => void;
  filter: string;
  selectedTags: Tag[];
  tags: Tag[];
  updateTags: UpdateTags;
  generateDropdownEntry: Props["generateDropdownEntry"];
}): React.ReactElement[] => {
  const dropdownItems = [];
  if (
    allowNewTags &&
    filter &&
    !tags.some((tag) => (tag.displayName || tag.name) === filter) &&
    !selectedTags.some((tag) => (tag.displayName || tag.name) === filter)
  ) {
    // Insert an extra item for creating a new tag if allowed and filter is not
    // an already existing tag
    const newTagItem = (
      <li className="tag-selector__dropdown-item" key={filter}>
        <Button
          appearance="base"
          className="tag-selector__dropdown-button u-break-word"
          data-testid="new-tag"
          onClick={(e) => {
            const cleanedFilter = sanitiseFilter(filter);
            if (onAddNewTag) {
              onAddNewTag(cleanedFilter.name)?.(e);
              setFilter("");
            } else {
              updateTags([...selectedTags, cleanedFilter]);
            }
          }}
          type="button"
        >
          <em>Create tag "{filter}"</em>
        </Button>
      </li>
    );
    dropdownItems.push(newTagItem);
  }

  const existingTagItems = tags
    .filter(
      (tag) =>
        (tag.displayName || tag.name).includes(filter) &&
        !selectedTags.some((selectedTag) => selectedTag.name === tag.name)
    )
    .map((tag) => {
      const highlightedName = filter
        ? highlightMatch(tag.displayName || tag.name, filter)
        : tag.displayName || tag.name;
      return (
        <li className="tag-selector__dropdown-item" key={tag.name}>
          <Button
            appearance="base"
            aria-label={tag.displayName}
            aria-selected={false}
            className="tag-selector__dropdown-button u-break-word"
            data-testid="existing-tag"
            onClick={() => {
              updateTags([...selectedTags, tag]);
            }}
            role="option"
            type="button"
          >
            {generateDropdownEntry?.(tag, highlightedName) ?? (
              <>
                {highlightedName}
                {tag.description && (
                  <div className="tag-selector__dropdown-item-description">
                    {tag.description}
                  </div>
                )}
              </>
            )}
          </Button>
        </li>
      );
    });

  return dropdownItems.concat(existingTagItems);
};

const generateSelectedItems = (
  selectedTags: Tag[],
  updateTags: UpdateTags,
  disabledTags: Tag[]
) =>
  selectedTags.map((tag) => {
    const isDisabled = disabledTags?.some(
      (disabledTag) => disabledTag.id === tag.id
    );

    return (
      <li className="tag-selector__selected-item" key={tag.name}>
        <Button
          appearance="base"
          className="tag-selector__selected-button u-break-word"
          data-testid="selected-tag"
          dense
          disabled={isDisabled}
          hasIcon
          onClick={() => {
            updateTags(
              selectedTags.filter((item) => item !== tag),
              false
            );
          }}
          type="button"
        >
          <span>{tag.name}</span>
          {!isDisabled && <i className="p-icon--close" />}
        </Button>
      </li>
    );
  });

export const TagSelector = ({
  allowNewTags = false,
  disabled,
  error,
  externalSelectedTags,
  generateDropdownEntry,
  help,
  initialSelected = [],
  label,
  onAddNewTag,
  onTagsUpdate,
  placeholder = "Tags",
  required = false,
  header,
  showSelectedTags = true,
  tags = [],
  disabledTags = [],
  ...props
}: Props): React.ReactElement => {
  const wrapperRef = useClickOutside<HTMLDivElement>(() => {
    setDropdownOpen(false);
  });
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [internalSelectedTags, setInternalSelectedTags] =
    useState(initialSelected);
  const useExternalTags = !!externalSelectedTags;
  const selectedTags = useExternalTags
    ? externalSelectedTags
    : internalSelectedTags;
  const [filter, setFilter] = useState("");
  const hasSelectedTags = showSelectedTags && selectedTags.length > 0;

  const updateTags = (newSelectedTags: Tag[], clearFilter = true) => {
    const sortedTags = newSelectedTags.sort((a, b) =>
      a.name.localeCompare(b.name)
    );
    if (!useExternalTags) {
      setInternalSelectedTags(sortedTags);
    }
    onTagsUpdate && onTagsUpdate(sortedTags);
    clearFilter && setFilter("");
  };

  const dropdownItems = generateDropdownItems({
    allowNewTags,
    onAddNewTag,
    setFilter,
    filter,
    selectedTags,
    tags,
    updateTags,
    generateDropdownEntry,
  });

  return (
    <div ref={wrapperRef}>
      <Field
        error={error}
        help={help}
        label={
          label ? (
            <span
              onClick={() => {
                setDropdownOpen(true);
              }}
            >
              {label}
            </span>
          ) : undefined
        }
        {...props}
      >
        <div className="tag-selector">
          {hasSelectedTags && (
            <ul className="tag-selector__selected-list">
              {generateSelectedItems(selectedTags, updateTags, disabledTags)}
            </ul>
          )}
          <Input
            aria-haspopup="listbox"
            aria-label={label ?? undefined}
            className={classNames("tag-selector__input", {
              "tags-selected": hasSelectedTags,
            })}
            disabled={disabled}
            name={TAG_SELECTOR_INPUT_NAME}
            onChange={(e) => {
              setFilter(e.target.value);
            }}
            onFocus={() => {
              setDropdownOpen(true);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (allowNewTags) {
                  const cleanedFilter = sanitiseFilter(filter);
                  if (onAddNewTag) {
                    onAddNewTag(cleanedFilter.name)?.(e);
                    setFilter("");
                  } else {
                    updateTags([...selectedTags, cleanedFilter]);
                  }
                }
              }
            }}
            placeholder={placeholder}
            required={required}
            type="text"
            value={filter}
          />
          {dropdownOpen && dropdownItems.length >= 1 && (
            <div className="tag-selector__dropdown" role="listbox">
              {header ? (
                <div className="tag-selector__dropdown-header">{header}</div>
              ) : null}
              <ul className="tag-selector__dropdown-list">{dropdownItems}</ul>
            </div>
          )}
        </div>
      </Field>
    </div>
  );
};

export default TagSelector;
