package tag

// targetSystemID is a Temporal logger tag for target
// system_id's
type targetSystemID string

// TargetSystemID provides a tag for the given system_id
func TargetSystemID(systemID string) targetSystemID {
	return targetSystemID(systemID)
}

// Key implements the temporal tag.Tag interface's Key() method
func (t targetSystemID) Key() string {
	return "target_system_id"
}

// Value implements the temporal tag.Tag interface's Value() method
func (t targetSystemID) Value() interface{} {
	return t
}
