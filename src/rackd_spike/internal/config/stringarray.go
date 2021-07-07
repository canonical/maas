package config

type StringArray []string

// UnmarshalYAML allows single value and arrays at the same field
//
// Both sintaxes are accepted:
//    maas_url: http://localhost:5240/MAAS
// and
//    maas_url: ['http://host1:5240/MAAS', 'http://host2:5240/MAAS']
//
func (a *StringArray) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var multi []string
	err := unmarshal(&multi)
	if err != nil {
		var single string
		err := unmarshal(&single)
		if err != nil {
			return err
		}
		*a = []string{single}
	} else {
		*a = multi
	}
	return nil
}

// MarshalYAML write single value and arrays depending on the array length
func (a StringArray) MarshalYAML() (interface{}, error) {
	if len(a) == 1 {
		return string(a[0]), nil
	}
	return []string(a), nil
}
