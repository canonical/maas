#!/bin/bash -e
#
# Prepare a MAAS release by doing the following:
#
# - update python project version
# - add debian/changelog entry for the release
# - tag the release in git
# - commit changes
#
# Usage:
#   ./version-bump.sh maas-version [ubuntu-distro]
#
# Example:
#   ./version-bump.sh 3.7.2 "noble"
#

export DEBFULLNAME="${DEBFULLNAME:-$(git config user.name)}"
export DEBEMAIL="${DEBEMAIL:-$(git config user.email)}"

git_tree_clean() {
    git diff-index --quiet HEAD
}

git_show_commit() {
    git show HEAD
}

version_changed() {
    local version major_version minor_version version_file
    version="$1"
    major_version=$(echo "$version" | cut --delimiter="." --fields=1)
    minor_version=$(echo "$version" | cut --delimiter="." --fields=2)

    if [[ "$major_version" -ge 3 && "$minor_version" -ge 6 ]]
    then
        version_file="pyproject.toml"
    else
        version_file="setup.cfg"
    fi

    ! git diff -s --exit-code "$version_file"
}

deb_version() {
    local version epoch
    version="$(echo "$1" | sed 's/a/~alpha/; tend; s/b/~beta/; tend; s/rc/~rc/; :end')"
    epoch="$(head -1 "debian/changelog" | sed -n 's|maas (\([1-9]*\):.*|\1|p')"
    if [ -n "$epoch" ]; then
	echo "${epoch}:${version}-0ubuntu1"
    else
	echo "${version}-0ubuntu1"
    fi
}

verbose_version() {
    echo "$1" | sed 's/a/ alpha/; tend; s/b/ beta/; tend; s/rc/ RC/; :end'
}

tag_version() {
    echo "$1" | sed 's/a/-alpha/; tend; s/b/-beta/; tend; s/rc/-rc/; :end'
}

replace_setup_version() {
    local version major_version minor_version
    version="$1"
    major_version=$(echo "$version" | cut --delimiter="." --fields=1)
    minor_version=$(echo "$version" | cut --delimiter="." --fields=2)

    if [[ "$major_version" -ge 3 && "$minor_version" -ge 6 ]]
    then
        sed -i 's/\bversion = .*$/version = "'"$version"'"/' pyproject.toml
    else
        sed -i 's/\bversion = .*$/version = '"$version"'/' setup.cfg
    fi    
}

add_debian_changelog() {
    local version="$1"
    local distro="$2"

    local distro_opt
    [ "$distro" ] && distro_opt="-D $distro" || distro_opt=""
    # shellcheck disable=SC2086
    dch $distro_opt -v "$(deb_version "$version")" \
        "New upstream release, MAAS $(verbose_version "$version")."
    dch -r ""
}

commit() {
    local version="$1"
    local message
    message="Prepare for $(verbose_version "$version") release"

    git commit -a -m "$message"
}

tag() {
    local version="$1"
    local tag="$(tag_version "$version")"
    git tag "$tag"
}

exit_error() {
    echo "$@" >&2
    exit 1
}


exit_usage() {
    local script
    script="$(basename "$0")"
    exit_error "Usage $script <major>.<minor>.<micro>[{a,b,rc}<num>] [ubuntu-distro]"
}


# Main
version="$1"
distro="$2"  # optional

maas_version="$(echo "${version}" | cut -d'.' -f-2)"
current_branch="$(git branch --show-current)"

if [ -z "$version" ]; then
    exit_usage
elif ! echo "$version" | grep -Eq "^[2-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$"; then
    echo "Invalid version!" >&2
    exit_usage
elif [[ "$maas_version" != *${current_branch}* ]]; then
    # Verify tags are created from the branch for that version if it exists.
    for branch in $(git ls-remote --heads origin | awk -F/ '{ print $3 }'); do
	if [[ "$maas_version" == *${branch}* ]]; then
	    exit_error "Branch ${branch} exists for version ${version}. Refusing to tag ${current_branch}."
	fi
    done
fi

if ! git_tree_clean; then
    exit_error "Git tree is not clean, please reset."
fi

replace_setup_version "$version"
if ! version_changed "$version"; then
    exit_error "The version is already set to $1"
fi
add_debian_changelog "$version" "$distro"
commit "$version"
tag "$version"
git_show_commit

