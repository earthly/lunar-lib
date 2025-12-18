from valid import check_valid
from pdb import check_pdb
from minreplicas import check_minreplicas
from resources import check_resources_requirements

def main():
    check_valid()
    check_pdb()
    check_minreplicas()
    check_resources_requirements()

if __name__ == "__main__":
    main()
