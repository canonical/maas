import PageContent from "@/app/base/components/PageContent";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useWindowTitle } from "@/app/base/hooks";

type Props = {
  includeSection?: boolean;
};

export enum Label {
  Title = "Error: Page not found",
}

const NotFound = ({ includeSection = false }: Props): React.ReactElement => {
  useWindowTitle(Label.Title);
  const message = `The requested URL ${window.location.pathname} was not found on this server.`;
  if (includeSection) {
    return (
      <PageContent
        aria-label={Label.Title}
        header={<SectionHeader title={Label.Title} />}
      >
        <h2 className="p-heading--5">{message}</h2>
      </PageContent>
    );
  }
  return (
    <div aria-label={Label.Title}>
      <h2 className="p-heading--5">{Label.Title}</h2>
      <p>{message}</p>
    </div>
  );
};

export default NotFound;
