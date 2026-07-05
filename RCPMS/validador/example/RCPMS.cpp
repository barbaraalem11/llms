#include "RCPMS.h"

//

// Funções auxiliares para limpeza e parsing
namespace Utils {
    // Remove caracteres indesejados (como colchetes)
    std::string cleanString(std::string input) {
        std::replace(input.begin(), input.end(), '[', ' ');
        std::replace(input.begin(), input.end(), ']', ' ');
        return input;
    }

    // Converte string "1, 2, 3" para vector<int>
    std::vector<int> parseVectorInt(std::string content) {
        std::vector<int> result;
        content = cleanString(content);
        std::stringstream ss(content);
        std::string segment;
        
        while (std::getline(ss, segment, ',')) {
            // Remove espaços em branco extras
            size_t first = segment.find_first_not_of(' ');
            if (std::string::npos == first) continue;
            
            try {
                result.push_back(std::stoi(segment));
            } catch (...) { continue; }
        }
        return result;
    }

    // Converte string "0=11, 12=26" para vector<pair<int,int>>
    std::vector<std::pair<int,int>> parseBlockPos(std::string content) {
        std::vector<std::pair<int,int>> result;
        content = cleanString(content);
        std::stringstream ss(content);
        std::string segment;

        while (std::getline(ss, segment, ',')) {
            size_t eqPos = segment.find('=');
            if (eqPos != std::string::npos) {
                try {
                    int key = std::stoi(segment.substr(0, eqPos));
                    int val = std::stoi(segment.substr(eqPos + 1));
                    result.push_back({key, val});
                } catch (...) { continue; }
            }
        }
        return result;
    }
}

RCPMS::RCPMS(std::string filename){

	std::string line; 
    std::ifstream ifs;
	ifs.open(filename);		

	if ( ifs.is_open()){
		
		getline(ifs,line);
		std::stringstream s(line);
		getline (s,line, ' ');
		numberJobs = std::stoi(line);
		getline (s,line, ' ');		
		numberMachine = std::stoi(line);		
		getline(s,line, ' ');		
		numberTools = std::stoi(line);
		
		getline(ifs,line);
		changeTax = std::stoi(line);
		
		getline(ifs,line);		
		std::stringstream ss(line);		

		while ( getline(ss,line, ' ')){
			JobTools.push_back(std::stoi(line));
		}
		
		getline(ifs,line);
		std::stringstream sss(line);		
		while ( getline(sss,line, ' ')){
			JobTax.push_back(std::stoi(line));
		}
					
	ifs.close();
	
	
	std::cout<<"Machines:"<< numberMachine<<"\n";
	std::cout<<"Jobs:"<< numberJobs<<"\n";
	std::cout<<"Tools:"<< numberTools<<"\n";
	std::cout<<"Change tax:"<< changeTax<<"\n";
	std::cout<<"Job tax:";
	for(auto& c:JobTax) std::cout<<c<<" ";
	std::cout<<"\n";
	std::cout<<"Jobs x Tools:";
	for(auto& c:JobTools) std::cout<<c<<" ";
	std::cout<<"\n";	
	
	}else{
		std::cout << "Could not open! \n";
	}	
}

RCPMS::~RCPMS(){	
}

// Função principal de leitura
solRCPMS RCPMS::loadResultFile(const std::string& filename) {
    solRCPMS data;
    std::ifstream file(filename);
    
    if (!file.is_open()) {
        std::cerr << "Erro ao abrir o arquivo: " << filename << std::endl;
        return data;
    }

    std::string line;
    std::string currentSection = "";
    std::string buffer = "";
    bool readingMultiline = false;

    while (std::getline(file, line)) {
        // 1. Parse do cabeçalho (makespan e início do bestS)
        if (line.find("simulation_run") != std::string::npos) {
            // Extrair makespan (evalSol)
            size_t mkPos = line.find("makespan :");
            if (mkPos != std::string::npos) {
                std::stringstream ss(line.substr(mkPos));
                std::string temp;
                ss >> temp >> temp >> data.evalSol; // Pula "makespan", pula ":", pega o valor
            }

            // Iniciar leitura do bestS (sol)
            size_t bestSPos = line.find("bestS :");
            if (bestSPos != std::string::npos) {
                size_t startBracket = line.find('[', bestSPos);
                if (startBracket != std::string::npos) {
                    buffer = line.substr(startBracket); // Pega do [ em diante
                    readingMultiline = true;
                    currentSection = "SOL";
                }
            }
        } 
        // 2. Verifica se encontrou seções específicas de conjuntos
        else if (line.find("cut start set:") != std::string::npos) {
            size_t pos = line.find('[');
            if (pos != std::string::npos) {
                data.cutStart = Utils::parseVectorInt(line.substr(pos));
            }
        }
        else if (line.find("cut end set:") != std::string::npos) {
            size_t pos = line.find('[');
            if (pos != std::string::npos) {
                data.cutEnd = Utils::parseVectorInt(line.substr(pos));
            }
        }
        else if (line.find("block pos set:") != std::string::npos) {
            size_t pos = line.find('[');
            if (pos != std::string::npos) {
                data.blockPos = Utils::parseBlockPos(line.substr(pos));
            }
        }
        // 3. Continuação de leitura multilinha (para bestS/sol)
        else if (readingMultiline && currentSection == "SOL") {
            buffer += line;
        }

        // Verifica se a seção multilinha terminou (encontrou ']')
        if (readingMultiline && buffer.find(']') != std::string::npos) {
            if (currentSection == "SOL") {
                data.sol = Utils::parseVectorInt(buffer);
            }
            readingMultiline = false;
            buffer = "";
            currentSection = "";
        }
    }

    file.close();
    return data;
}

double RCPMS::evaluate(solRCPMS sol){
	
	int max = 0;
	int m = 0;
	int cm = -1;	
	
	std::queue<int> exec;

	std::vector<int> mSpam(numberMachine,0); //makespan da maquina
	std::vector<int> magazine(numberMachine,0);	//magazine atual da maquina
	std::vector<int> p(numberMachine,0);	
	std::vector<int> fSpamStart(numberTools,0);
	std::vector<int> fSpamEnd(numberTools,0);
	std::vector<int> fMachine(numberTools,-1);
	
	
	for(int i = 0; i < numberMachine;++i){
		magazine[i] = JobTools[sol.sol[sol.cutStart[i]]];
		exec.push(i);
	}

	
	while(!exec.empty()){
		m = exec.front();
		exec.pop();
							
		// verifica se ainda tem tarefas a ser processada
		if((sol.cutStart[m]+p[m]) < sol.cutEnd[m]){
				
			// verifica se o makespam onde a ferramenta foi utilizada é maior que o makespam da maquina
			if((fSpamStart[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] <= mSpam[m]) && (fSpamEnd[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] > mSpam[m])){
				// o makespam da maquina recebe o makespam da ferramenta
				mSpam[m] = fSpamEnd[JobTools[sol.sol[sol.cutStart[m]+p[m]]]];
			//	std::cout<<"Adionar gap \n";

			}else{				
				fSpamStart[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] = mSpam[m];
			}
			
			// Verifica se há troca
			if((magazine[m] != JobTools[sol.sol[sol.cutStart[m]+p[m]]]) || ((fMachine[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] != m) && (fMachine[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] != -1))){
				mSpam[m] += changeTax;
			}
				
			mSpam[m] += JobTax[sol.sol[sol.cutStart[m]+p[m]]];
				
			magazine[m] = JobTools[sol.sol[sol.cutStart[m]+p[m]]];
			fSpamEnd[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] = mSpam[m];
			fMachine[JobTools[sol.sol[sol.cutStart[m]+p[m]]]] = m;
				
		}
		
		++p[m];
	
		if(exec.empty()){
			int min = std::numeric_limits<int>::max();
			int machine = -1;
		
			for(int i = 0; i < numberMachine;++i){
				if((min >= mSpam[i]) && ((sol.cutStart[i]+p[i]) < sol.cutEnd[i])){
					machine = i;
					min = mSpam[i];
				}
				if(max < mSpam[i]){ 
					max = mSpam[i];
					cm = i;
				} 			
			}
			
			if(machine != -1) exec.push(machine);
		}
	}
	
		
	return max;
}

int RCPMS::criticalMachine(solRCPMS* sol){
	
	int max = 0;
	int m = 0;
	int cm = -1;	
	
	std::queue<int> exec;

	std::vector<int> mSpam(numberMachine,0); //makespan da maquina
	std::vector<int> magazine(numberMachine,0);	//magazine atual da maquina
	std::vector<int> p(numberMachine,0);	
	std::vector<int> fSpamStart(numberTools,0);
	std::vector<int> fSpamEnd(numberTools,0);
	std::vector<int> fMachine(numberTools,-1);
	
	
	for(int i = 0; i < numberMachine;++i){
		magazine[i] = JobTools[(*sol).sol[(*sol).cutStart[i]]];
		exec.push(i);
	}

	
	while(!exec.empty()){
		m = exec.front();
		exec.pop();
							
		// verifica se ainda tem tarefas a ser processada
		if(((*sol).cutStart[m]+p[m]) < (*sol).cutEnd[m]){
				
			// verifica se o makespam onde a ferramenta foi utilizada é maior que o makespam da maquina
			if((fSpamStart[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] <= mSpam[m]) && (fSpamEnd[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] > mSpam[m])){
				// o makespam da maquina recebe o makespam da ferramenta
				mSpam[m] = fSpamEnd[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]];
			//	std::cout<<"Adionar gap \n";

			}else{				
				fSpamStart[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] = mSpam[m];
			}
			
			// Verifica se há troca
			if((magazine[m] != JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]) || ((fMachine[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] != m) && (fMachine[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] != -1))){
				mSpam[m] += changeTax;
			}
				
			mSpam[m] += JobTax[(*sol).sol[(*sol).cutStart[m]+p[m]]];
				
			magazine[m] = JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]];
			fSpamEnd[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] = mSpam[m];
			fMachine[JobTools[(*sol).sol[(*sol).cutStart[m]+p[m]]]] = m;
				
		}
		
		++p[m];
	
		if(exec.empty()){
			int min = std::numeric_limits<int>::max();
			int machine = -1;
		
			for(int i = 0; i < numberMachine;++i){
				if((min >= mSpam[i]) && (((*sol).cutStart[i]+p[i]) < (*sol).cutEnd[i])){
					machine = i;
					min = mSpam[i];
				}
				if(max < mSpam[i]){ 
					max = mSpam[i];
					cm = i;
				} 			
			}
			
			if(machine != -1) exec.push(machine);
		}
	}
	
	
	(*sol).evalSol = max;
	
	return cm;
}


