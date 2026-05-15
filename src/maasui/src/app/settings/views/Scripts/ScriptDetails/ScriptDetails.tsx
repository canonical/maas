import { useContext, useEffect, useRef } from "react";

import {
  Button,
  Code,
  Col,
  Icon,
  Row,
  Spinner,
} from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import { useDispatch, useSelector } from "react-redux";

import FileContext from "@/app/base/file-context";
import { scriptActions } from "@/app/store/script";
import scriptSelectors from "@/app/store/script/selectors";
import type { Script } from "@/app/store/script/types";

type Props = {
  id: Script["id"];
  isCollapsible?: boolean;
  onCollapse?: () => void;
};

const ScriptDetails = ({
  id,
  isCollapsible,
  onCollapse,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const loading = useSelector(scriptSelectors.loading);
  const scriptKey = useRef(nanoid());
  const fileContext = useContext(FileContext);
  const script = fileContext.get(scriptKey.current);

  useEffect(() => {
    if (id) {
      dispatch(scriptActions.get(id, scriptKey.current));
    }
  }, [dispatch, id]);

  // Clean up the requested files when the component unmounts.
  useEffect(
    () => () => {
      fileContext.remove(scriptKey.current);
    },
    [fileContext]
  );

  if (loading) {
    return <Spinner />;
  }

  if (!script) {
    return <>Script could not be found</>;
  }

  return (
    <>
      <Row>
        <Col size={10}>
          <Code className="u-no-margin--bottom">{script}</Code>
        </Col>
      </Row>
      {isCollapsible && (
        <Row>
          <Col className="u-flex--end" emptyLarge={8} size={4}>
            <Button
              appearance="link"
              className="u-flex--between u-flex--align-center script-details--collapse-button"
              dense
              onClick={onCollapse}
            >
              <span className="u-nudge-left--small">Close snippet</span>
              <Icon className="" name="chevron-up" />
            </Button>
          </Col>
        </Row>
      )}
    </>
  );
};

export default ScriptDetails;
