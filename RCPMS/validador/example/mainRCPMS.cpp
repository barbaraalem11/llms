/*
 * main.cpp
 * 
 * Copyright 2021 André Luis <André Luis@DESKTOP-HDL2CBS>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
 * MA 02110-1301, USA.
 * 
 * 
 */
#include <cstdlib>
#include "RCPMS.h"


using namespace std;

int main(int argc, char* argv[])
{	
	vector<std::string> arguments(argv + 1, argv + argc);
	// Instance file name
	std::string fn = arguments[0];

	// result file name
	std::string fr = arguments[1];
	
	// Create SSP object
	RCPMS* prob = new RCPMS(fn);
	
	solRCPMS resultado = prob->loadResultFile(fr);
	// Exibindo os resultados para conferência
    std::cout << "=== Leitura Concluida ===" << std::endl;
    std::cout << "EvalSol (Makespan lido): " << resultado.evalSol << " EvalSol Calculado: "<< prob->evaluate(resultado)<< std::endl;
    
    std::cout << "Sol (Tamanho: " << resultado.sol.size() << "): ";
    for(size_t i = 0; i < std::min((size_t)10, resultado.sol.size()); ++i) std::cout << resultado.sol[i] << " ";
    std::cout << "..." << std::endl;

    std::cout << "CutStart (Tamanho: " << resultado.cutStart.size() << "): ";
    for(int v : resultado.cutStart) std::cout << v << " ";
    std::cout << std::endl;
    
    std::cout << "CutEnd (Tamanho: " << resultado.cutEnd.size() << "): ";
    for(int v : resultado.cutEnd) std::cout << v << " ";
    std::cout << std::endl;

    std::cout << "BlockPos (Tamanho: " << resultado.blockPos.size() << "): ";
    for(auto p : resultado.blockPos) std::cout << "[" << p.first << "=" << p.second << "] ";
    std::cout << std::endl;	
	
	return 0;
}

